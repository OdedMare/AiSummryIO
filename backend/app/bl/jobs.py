"""Bounded background queue. Interactive follow-ups have priority."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.common.logging_setup import abandoned_workers, trace

_log = trace("jobs")

# How often the watchdog reports in-flight runs, and the age at which one is
# called out as stuck. The default package timeout is 120s, so a run past
# 180s has outlived the bound that was supposed to cap it.
_WATCHDOG_SECONDS = 15
_STUCK_SECONDS = 180


class JobRunner:
    def __init__(self, repository, service, workers=4):
        self._repository = repository
        self._service = service
        worker_count = max(2, workers)
        self._full_capacity = worker_count - 1
        self._full_pool = ThreadPoolExecutor(max_workers=self._full_capacity)
        self._follow_up_pool = ThreadPoolExecutor(max_workers=1)
        self._submitted = set()
        # Runs currently inside `_execute`, so saturation can be reported as
        # "3 of 3 busy" rather than inferred from silence.
        self._running = {}
        self._lock = threading.Lock()
        _log.info(
            "JobRunner ready full_pool=%d follow_up_pool=1 (from "
            "max_parallel_workflows=%d)", self._full_capacity, workers,
        )
        self._start_watchdog()

    def _start_watchdog(self) -> None:
        """Report long-running runs every 15s.

        A hang inside flunks emits nothing at all — no progress, no error —
        so without a ticking observer the console simply goes quiet and the
        run's age is invisible. Daemon, so it never holds up shutdown.
        """
        def watch():
            while True:
                time.sleep(_WATCHDOG_SECONDS)
                self._report_stuck()

        threading.Thread(
            target=watch, name="job-watchdog", daemon=True
        ).start()

    def _report_stuck(self) -> None:
        now = time.time()
        with self._lock:
            ages = [(run_id, now - at) for run_id, at in self._running.items()]
        if not ages:
            return
        for run_id, age in sorted(ages, key=lambda item: -item[1]):
            if age < _WATCHDOG_SECONDS:
                continue
            _log.warning(
                "run=%s still running after %.0fs%s",
                run_id, age,
                " — LIKELY STUCK" if age >= _STUCK_SECONDS else "",
            )
        abandoned = abandoned_workers()
        if abandoned:
            _log.error(
                "%d FLAPI worker thread(s) abandoned so far; full pool "
                "capacity is %d. When these match, no run can ever start.",
                abandoned, self._full_capacity,
            )

    def recover(self) -> None:
        queued = self._repository.queued_runs()
        _log.info("recovering %d queued run(s) from a previous start", len(queued))
        for run in queued:
            self.submit(run["id"])

    def submit(self, run_id: str) -> None:
        run = self._repository.get_run(run_id)
        with self._lock:
            if run_id in self._submitted:
                _log.debug("run %s already submitted, ignoring", run_id)
                return
            self._submitted.add(run_id)
            busy = len(self._running)
        follow_up = run["kind"] == "follow_up"
        pool = self._follow_up_pool if follow_up else self._full_pool
        capacity = 1 if follow_up else self._full_capacity
        _log.info(
            "queued run=%s kind=%s pool=%s busy=%d/%d",
            run_id, run["kind"], "follow_up" if follow_up else "full",
            busy, capacity,
        )
        if not follow_up and busy >= capacity:
            # Nothing is broken yet, but the run will not start until a
            # worker frees up — and an abandoned flunks thread never does.
            _log.warning(
                "full pool SATURATED (%d/%d busy) — run %s will wait. If "
                "workers were abandoned by FLAPI timeouts this never starts.",
                busy, capacity, run_id,
            )
        pool.submit(self._execute, run_id)

    def _execute(self, run_id: str) -> None:
        started = time.time()
        with self._lock:
            self._running[run_id] = started
            busy = len(self._running)
        _log.info("START run=%s (busy=%d)", run_id, busy)
        try:
            run = self._repository.update_run(run_id, status="running")
            conversation = self._repository.get_conversation(
                run["conversation_id"]
            )
            _log.info(
                "run=%s kind=%s root_id=%s", run_id, run["kind"],
                conversation.get("root_id"),
            )

            def progress(
                completed, total, sections, agent_trace=None, phase=None
            ):
                _log.info(
                    "run=%s progress %d/%d (%.1fs elapsed)",
                    run_id, completed, total, time.time() - started,
                )
                payload = {
                    "completed": completed,
                    "total": total,
                    "sections": sections,
                }
                if agent_trace is not None:
                    payload["agent_trace"] = agent_trace
                if phase:
                    payload["phase"] = phase
                self._repository.update_run(run_id, progress=payload)

            if run["kind"] == "full":
                result = self._service.full_summary(
                    run, conversation, progress
                )
            else:
                result = self._service.follow_up(
                    run, conversation, progress
                )
            status = "partial" if result.get("partial") else "completed"
            self._repository.update_run(
                run_id, status=status, result=result,
                finished_at=datetime.now(timezone.utc),
            )
            _log.info(
                "DONE  run=%s status=%s in %.2fs",
                run_id, status, time.time() - started,
            )
        except Exception as exc:
            # `exception` so the traceback reaches the console: this is the
            # only place a background failure is observable, and the run row
            # keeps just the message.
            _log.exception(
                "FAILED run=%s after %.2fs %s: %s",
                run_id, time.time() - started, type(exc).__name__, exc,
            )
            self._repository.update_run(
                run_id, status="failed", error=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            with self._lock:
                self._submitted.discard(run_id)
                self._running.pop(run_id, None)
                remaining = len(self._running)
            _log.debug("run=%s released worker (busy=%d)", run_id, remaining)
