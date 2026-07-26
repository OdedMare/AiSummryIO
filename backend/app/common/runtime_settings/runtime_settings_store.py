import hashlib
import hmac
import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from app.common.config.settings import Settings
from app.common.runtime_settings.normalizers import (
    normalize_database_url,
    normalize_http_url,
)
from app.common.runtime_settings.runtime_settings import RuntimeSettings

_SECRET_FIELDS = {
    "database_password", "openai_api_key", "flapi_token",
    "admin_password_hash", "cookie_secret",
}


class RuntimeSettingsStore:
    def __init__(self, env: Settings):
        self._path = Path(env.runtime_settings_file)
        self._settings = RuntimeSettings(
            database_url=env.database_url,
            database_user=env.database_user,
            database_password=env.database_password,
            database_host=env.database_host,
            database_port=env.database_port,
            database_name=env.database_name,
            llm_model=env.llm_model,
            llm_diet_mode=env.llm_diet_mode,
            llm_base_url=env.llm_base_url,
            openai_api_key=env.openai_api_key,
            flapi_username=env.flapi_username,
            flapi_token=env.flapi_token,
            flapi_verify_tls=env.flapi_verify_tls,
            max_parallel_workflows=env.max_parallel_workflows,
            package_timeout_seconds=env.package_timeout_seconds,
            conversation_retention_days=env.conversation_retention_days,
            log_retention_days=env.log_retention_days,
            admin_password_hash=env.admin_password_hash,
            cookie_secret=env.cookie_secret,
        )
        if self._path.exists():
            self._apply(json.loads(self._path.read_text("utf-8")), False)
        changed = False
        if not self._settings.cookie_secret:
            self._settings.cookie_secret = os.urandom(32).hex()
            changed = True
        if env.admin_password and not self._settings.admin_password_hash:
            self._settings.admin_password_hash = hash_password(env.admin_password)
            changed = True
        if changed:
            self._persist()

    def get(self) -> RuntimeSettings:
        return self._settings

    def public(self) -> dict:
        data = asdict(self._settings)
        for key in _SECRET_FIELDS:
            data[key] = "********" if data.get(key) else ""
        return data

    def update(self, patch: dict) -> RuntimeSettings:
        self._apply(patch, True)
        self._persist()
        return self._settings

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(asdict(self._settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _apply(self, patch: dict, strict: bool) -> None:
        known = {item.name for item in fields(RuntimeSettings)}
        for key, value in patch.items():
            if key not in known or value == "********" or value is None:
                continue
            try:
                if key == "database_url":
                    value = normalize_database_url(value)
                elif key == "llm_base_url" and value:
                    value = normalize_http_url(value, key)
                elif key in (
                    "max_parallel_workflows", "package_timeout_seconds",
                    "conversation_retention_days", "log_retention_days",
                ):
                    value = max(1, int(value))
            except (TypeError, ValueError):
                if strict:
                    raise
                continue
            setattr(self._settings, key, value)


def hash_password(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32
    )
    return "scrypt$16384$8$1$%s$%s" % (salt.hex(), digest.hex())


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, n, r, p, salt, expected = encoded.split("$")
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt),
            n=int(n), r=int(r), p=int(p), dklen=32,
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (TypeError, ValueError):
        return False
