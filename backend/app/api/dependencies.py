"""Shared FastAPI dependencies for cookie and API-token callers.

Browsers authenticate with the signed HttpOnly cookies they already had.
Scripts send the configured token as ``X-API-Key`` or
``Authorization: Bearer``. Both paths resolve to the same identities here, so
a route never needs to know which kind of client it is serving.
"""

import uuid

from fastapi import Cookie, Header, Response

from app.api.auth import (
    api_token_matches, bearer_token, require_admin_token, session_signature,
    verify_session,
)
from app.common.errors import AuthError

# One stable session for every API-token caller. Programmatic clients keep no
# cookie jar, so without this each call would strand its conversation under a
# fresh random session and be unable to read it back.
API_SESSION_ID = "api-token-session"

_SESSION_COOKIE = "aisummry_session"
_SESSION_MAX_AGE = 30 * 24 * 60 * 60


def _presented_token(api_key: str, authorization: str) -> str:
    return api_key.strip() or bearer_token(authorization)


def make_dependencies(store):
    """Build the dependency callables bound to one settings store."""

    def admin_dependency(
        aisummry_admin: str = Cookie(default=""),
        x_api_key: str = Header(default=""),
        authorization: str = Header(default=""),
    ) -> None:
        """Allow FDE routes for an admin cookie or the API token."""
        if api_token_matches(
            store, _presented_token(x_api_key, authorization)
        ):
            return
        require_admin_token(store, aisummry_admin)

    def user_session(
        aisummry_session: str = Cookie(default=""),
        x_api_key: str = Header(default=""),
        authorization: str = Header(default=""),
    ) -> str:
        """Resolve the caller's conversation identity.

        A valid cookie wins, so a browser that also sends the token keeps its
        own history. An unsigned or tampered cookie falls through rather than
        raising: anonymous users are simply issued a new session.
        """
        if aisummry_session:
            try:
                return verify_session(store, aisummry_session)
            except AuthError:
                pass
        if api_token_matches(
            store, _presented_token(x_api_key, authorization)
        ):
            return API_SESSION_ID
        return str(uuid.uuid4())

    def set_session_cookie(response: Response, session_id: str) -> None:
        if session_id == API_SESSION_ID:
            return
        response.set_cookie(
            _SESSION_COOKIE, session_signature(store, session_id),
            httponly=True, samesite="lax", max_age=_SESSION_MAX_AGE,
        )

    return admin_dependency, user_session, set_session_cookie
