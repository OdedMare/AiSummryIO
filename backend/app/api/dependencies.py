"""Shared FastAPI dependencies for conversation identity.

The service has no caller credential. FDE routes are open, so
``admin_dependency`` is a no-op kept only so routes and the composition root
keep one guard seam to reinstate authentication through. Conversation identity
comes from the signed HttpOnly session cookie a browser already had.
"""

import uuid

from fastapi import Cookie, Response

from app.api.auth import session_signature, verify_session
from app.common.errors import AuthError

_SESSION_COOKIE = "aisummry_session"
_SESSION_MAX_AGE = 30 * 24 * 60 * 60


def make_dependencies(store):
    """Build the dependency callables bound to one settings store."""

    def admin_dependency() -> None:
        """Allow every caller: FDE routes are unauthenticated."""

    def user_session(aisummry_session: str = Cookie(default="")) -> str:
        """Resolve the caller's conversation identity.

        An unsigned or tampered cookie falls through rather than raising:
        anonymous users are simply issued a new session.
        """
        if aisummry_session:
            try:
                return verify_session(store, aisummry_session)
            except AuthError:
                pass
        return str(uuid.uuid4())

    def set_session_cookie(response: Response, session_id: str) -> None:
        response.set_cookie(
            _SESSION_COOKIE, session_signature(store, session_id),
            httponly=True, samesite="lax", max_age=_SESSION_MAX_AGE,
        )

    return admin_dependency, user_session, set_session_cookie
