"""Anonymous-session signing.

The service carries no caller credential: FDE routes are unauthenticated and
rely on the deployment only being reachable from a trusted network. What
remains here signs the conversation cookie, which identifies a chat history
but grants no privileges.
"""

import hashlib
import hmac

from app.common.errors import AuthError


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
