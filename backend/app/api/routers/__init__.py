"""Routers grouped by resource, assembled onto the app by ``main.py``.

Every route is served under both ``/api`` and the explicit ``/api/v1``. The
unversioned prefix is what the existing frontend calls; ``/api/v1`` is the
stable path for programmatic clients, so the browser and a script address the
same handlers.
"""

from fastapi import APIRouter

from app.api.routers import (
    admin, agent_content, conversations, feedback, health, packages,
    summaries, workflows,
)

_BUILDERS = (
    health, summaries, conversations, feedback, admin, packages, workflows,
    agent_content,
)

API_PREFIX = "/api"
VERSIONED_PREFIX = "/api/v1"


def api_router(context) -> APIRouter:
    """One router holding every resource router, without a prefix."""
    router = APIRouter()
    for module in _BUILDERS:
        router.include_router(module.build(context))
    return router


def register(app, context) -> None:
    """Mount the API twice: unversioned for the UI, /v1 for API clients.

    Each prefix gets its own freshly built routers. Including one router
    object under two prefixes would register the same route objects twice and
    duplicate them in the OpenAPI schema.
    """
    app.include_router(api_router(context), prefix=VERSIONED_PREFIX)
    app.include_router(
        api_router(context), prefix=API_PREFIX, include_in_schema=False
    )
