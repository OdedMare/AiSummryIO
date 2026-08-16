"""Liveness and database reachability."""

from fastapi import APIRouter

from app.common.errors import UnavailableError
from app.common.logging_setup import abandoned_workers


def build(context) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {
            "status": "ok",
            **context.repository.health(),
            "abandoned_workers": abandoned_workers(),
            "worker_capacity": context.jobs.capacity(),
        }

    @router.get("/health/live")
    def live():
        """Fail once abandoned threads have eaten the whole pool.

        A `tcpSocket` probe stays green in exactly this state — the port is
        open, the process is healthy, and no run will ever start again. This
        is the one condition worth restarting a pod over, so it is served
        apart from `/health`, which must keep reporting for a human even when
        the answer is bad.
        """
        abandoned = abandoned_workers()
        capacity = context.jobs.capacity()
        if capacity and abandoned >= capacity:
            raise UnavailableError(
                "כל תהליכוני העבודה אבדו בעקבות חריגות זמן מול FLAPI "
                "(%d מתוך %d); נדרשת הפעלה מחדש." % (abandoned, capacity)
            )
        return {"status": "ok"}

    return router
