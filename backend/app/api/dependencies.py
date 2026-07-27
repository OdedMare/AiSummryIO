"""Shared FastAPI dependencies for cookie and API-token callers.

FDE routes are guarded by the configured API token alone, sent as
``X-API-Key`` or ``Authorization: Bearer``. Conversation identity still comes
from the signed HttpOnly session cookie a browser already had, so a route
never needs to know which kind of client it is serving.
"""

import uuid

from fastapi import Cookie, Header, Response

from app.api.auth import (
    api_token_matches, bearer_token, session_signature, verify_session,
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
        x_api_key: str = Header(default=""),
        authorization: str = Header(default=""),
    ) -> None:
        """Allow FDE routes only for the configured API token."""
        if not api_token_matches(
            store, _presented_token(x_api_key, authorization)
        ):
            raise AuthError("נדרש טוקן FDE")

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
