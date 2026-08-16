"""Persistent coordinator that admits evaluation cases to ``JobRunner``."""

import threading

from app.common.logging_setup import trace

_log = trace("evaluations")
_POLL_SECONDS = 0.75


class EvaluationRunner:
    """Keep one shared batch moving without queueing all of it in memory."""

    def __init__(self, repository, jobs, capacity: int):
        self._repository = repository
        self._jobs = jobs
        self._capacity = max(1, capacity)
        self._wake = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def recover(self) -> None:
        """Start the daemon once; persisted state is the recovery source."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._wake.set()
                return
            self._thread = threading.Thread(
                target=self._loop, name="evaluation-runner", daemon=True
            )
            self._thread.start()
        self._wake.set()

    def notify(self) -> None:
        self._wake.set()

    def tick(self) -> None:
        """Advance one batch; public so the state machine is easy to test."""
        batch = self._repository.active_evaluation_batch()
        if not batch:
            return
        batch_id = batch["id"]
        active = int(batch["queued"]) + int(batch["running"])
        pending = int(batch["pending"])

        if batch["status"] == "pausing":
            if active == 0:
                self._repository.settle_evaluation(
                    batch_id, "completed" if pending == 0 else "paused"
                )
            return
        if batch["status"] == "stopping":
            if active == 0:
                self._repository.settle_evaluation(batch_id, "stopped")
            return
        if batch["status"] != "running":
            return
        if not pending and not active:
            self._repository.settle_evaluation(batch_id, "completed")
            return

        while active < self._capacity and pending:
            started = self._repository.start_next_evaluation_case(batch_id)
            if not started:  # Cooldown has not elapsed, or Pause won the race.
                return
            try:
                self._jobs.submit(started["run_id"])
            except Exception as error:
                _log.exception(
                    "failed to submit evaluation case=%s", started["case_id"]
                )
                self._repository.fail_evaluation_case(
                    started["case_id"], str(error)
                )
                self._repository.update_run(
                    started["run_id"], status="failed", error=str(error)
                )
            active += 1
            pending -= 1

    def _loop(self) -> None:
        while True:
            self._wake.wait(_POLL_SECONDS)
            self._wake.clear()
            try:
                self.tick()
            except Exception:
                _log.exception("evaluation coordinator tick failed")
