"""Bounded background queue. Interactive follow-ups have priority."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


class JobRunner:
    def __init__(self, repository, service, workers=4):
        self._repository = repository
        self._service = service
        worker_count = max(2, workers)
        self._full_pool = ThreadPoolExecutor(max_workers=worker_count - 1)
        self._follow_up_pool = ThreadPoolExecutor(max_workers=1)
        self._submitted = set()
        self._lock = threading.Lock()

    def recover(self) -> None:
        for run in self._repository.queued_runs():
            self.submit(run["id"])

    def submit(self, run_id: str) -> None:
        run = self._repository.get_run(run_id)
        with self._lock:
            if run_id in self._submitted:
                return
            self._submitted.add(run_id)
        pool = (
            self._follow_up_pool
            if run["kind"] == "follow_up"
            else self._full_pool
        )
        pool.submit(self._execute, run_id)

    def _execute(self, run_id: str) -> None:
        try:
            run = self._repository.update_run(run_id, status="running")
            conversation = self._repository.get_conversation(
                run["conversation_id"]
            )

            def progress(completed, total, sections):
                self._repository.update_run(
                    run_id,
                    progress={
                        "completed": completed,
                        "total": total,
                        "sections": sections,
                    },
                )

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
        except Exception as exc:
            self._repository.update_run(
                run_id, status="failed", error=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            with self._lock:
                self._submitted.discard(run_id)
