import hashlib
import hmac
import time

from app.common.errors import AuthError
from app.common.runtime_settings.runtime_settings_store import verify_password

_ADMIN_TTL_SECONDS = 12 * 60 * 60


def admin_token(store) -> str:
    timestamp = str(int(time.time()))
    signature = _sign(store, "admin:" + timestamp)
    return timestamp + "." + signature


def require_admin_token(store, token: str) -> None:
    try:
        timestamp, signature = token.split(".", 1)
        age = time.time() - int(timestamp)
    except (AttributeError, TypeError, ValueError):
        raise AuthError("נדרשת התחברות FDE")
    expected = _sign(store, "admin:" + timestamp)
    if age < 0 or age > _ADMIN_TTL_SECONDS or not hmac.compare_digest(
        signature, expected
    ):
        raise AuthError("פג תוקף ההתחברות")


def login(store, password: str) -> str:
    encoded = store.get().admin_password_hash
    if not encoded:
        raise AuthError("סיסמת FDE טרם הוגדרה בשרת")
    if not verify_password(password, encoded):
        raise AuthError("סיסמה שגויה")
    return admin_token(store)


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

