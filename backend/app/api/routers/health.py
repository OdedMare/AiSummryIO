"""Liveness and database reachability."""

from fastapi import APIRouter


def build(context) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {"status": "ok", **context.repository.health()}

    return router
