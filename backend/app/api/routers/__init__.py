"""Routers grouped by resource, assembled onto the app by ``main.py``.

Every route is served under both ``/api`` and the explicit ``/api/v1``. The
unversioned prefix is what the existing frontend calls; ``/api/v1`` is the
stable path for programmatic clients, so the browser and a script address the
same handlers.
"""

from fastapi import APIRouter

from app.api.routers import (
    admin, agent_content, conversations, evaluations, feedback, health, packages,
    summaries, workflows,
)

_BUILDERS = (
    health, summaries, conversations, feedback, admin, packages, workflows,
    agent_content, evaluations,
)

API_PREFIX = "/api"
VERSIONED_PREFIX = "/api/v1"


def resource_routers(context):
    """A freshly built router per resource module."""
    return [module.build(context) for module in _BUILDERS]


def register(app, context) -> None:
    """Mount the API twice: unversioned for the UI, /v1 for API clients.

    Each resource router is included directly on the app rather than nested
    inside one parent router — FastAPI resolves a router included into
    another router lazily, and mounting that parent under a prefix drops the
    nested routes. Each prefix also gets its own freshly built routers, since
    including one router object twice would duplicate its routes.
    """
    for router in resource_routers(context):
        app.include_router(router, prefix=VERSIONED_PREFIX)
    for router in resource_routers(context):
        app.include_router(
            router, prefix=API_PREFIX, include_in_schema=False
        )
