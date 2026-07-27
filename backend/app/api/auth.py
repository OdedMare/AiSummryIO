"""API-token and anonymous-session authentication."""

import hashlib
import hmac

from app.common.errors import AuthError


def api_token_matches(store, token: str) -> bool:
    """True when a programmatic client presented the configured API token.

    Compared with ``compare_digest`` so a wrong token cannot be recovered by
    timing. An unset token never matches, otherwise clearing the setting
    would silently open every route to an empty header.
    """
    expected = store.get().api_token
    if not expected or not token:
        return False
    return hmac.compare_digest(token, expected)


def bearer_token(header: str) -> str:
    """Extract the credential from an ``Authorization: Bearer <token>``."""
    if not header:
        return ""
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


def session_signature(store, session_id: str) -> str:
    return session_id + "." + _sign(store, "session:" + session_id)


def verify_session(store, token: str) -> str:
    try:
        session_id, signature = token.split(".", 1)
    except (AttributeError, ValueError):
        raise AuthError("session")
    if not hmac.compare_digest(
        signature, _sign(store, "session:" + session_id)
    ):
        raise AuthError("session")
    return session_id


def _sign(store, value: str) -> str:
    secret = store.get().cookie_secret.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()
