import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from app.common.config.settings import Settings
from app.common.runtime_settings.normalizers import (
    MASKED_SECRET,
    extract_url_schema,
    normalize_database_schema,
    normalize_database_url,
    normalize_llm_base_url,
)
from app.common.runtime_settings.runtime_settings import RuntimeSettings

_SECRET_FIELDS = {
    "database_password", "openai_api_key", "flapi_token", "cookie_secret",
}

# Fields where None/empty means "clear the value", not "keep current".
# Without this, an emptied base URL or port could never be unset from the UI.
_NULLABLE = ("database_port", "llm_base_url", "flapi_username")


class RuntimeSettingsStore:
    def __init__(self, env: Settings):
        self._path = Path(env.runtime_settings_file)
        self._settings = RuntimeSettings(
            # Env values get the same normalization as UI edits, so a
            # jdbc: URL works however it is supplied.
            database_url=_safe_database_url(env.database_url),
            database_user=env.database_user,
            database_password=env.database_password,
            database_host=env.database_host,
            database_port=env.database_port,
            database_name=env.database_name,
            database_schema=_safe_schema(
                extract_url_schema(env.database_url) or env.database_schema
            ),
            llm_model=env.llm_model,
            llm_diet_mode=env.llm_diet_mode,
            llm_repetition_penalty=_clamp_penalty(env.llm_repetition_penalty),
            llm_timeout_seconds=env.llm_timeout_seconds,
            llm_base_url=env.llm_base_url,
            openai_api_key=env.openai_api_key,
            flapi_username=env.flapi_username,
            flapi_token=env.flapi_token,
            flapi_verify_tls=env.flapi_verify_tls,
            max_parallel_workflows=env.max_parallel_workflows,
            agent_max_rounds=min(5, max(0, env.agent_max_rounds)),
            package_timeout_seconds=env.package_timeout_seconds,
            conversation_idle_minutes=env.conversation_idle_minutes,
            conversation_retention_days=env.conversation_retention_days,
            log_retention_days=env.log_retention_days,
            cookie_secret=env.cookie_secret,
        )
        if self._path.exists():
            self._apply(json.loads(self._path.read_text("utf-8")), False)
        if not self._settings.cookie_secret:
            self._settings.cookie_secret = os.urandom(32).hex()
            self._persist()

    def get(self) -> RuntimeSettings:
        return self._settings

    def public(self) -> dict:
        data = asdict(self._settings)
        for key in _SECRET_FIELDS:
            data[key] = MASKED_SECRET if data.get(key) else ""
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
            if key not in known or value == MASKED_SECRET:
                continue
            if key in _NULLABLE and (value is None or value == ""):
                setattr(self._settings, key, None)
                continue
            if value is None:
                continue
            try:
                if key == "database_url":
                    # A pasted jdbc:...?currentSchema=x sets the schema too,
                    # unless the patch names one explicitly.
                    in_url = extract_url_schema(value)
                    if in_url and not patch.get("database_schema"):
                        self._settings.database_schema = (
                            normalize_database_schema(in_url)
                        )
                    value = normalize_database_url(value)
                elif key == "database_schema":
                    value = normalize_database_schema(value)
                elif key == "llm_base_url":
                    value = normalize_llm_base_url(value)
                elif key == "agent_max_rounds":
                    value = min(5, max(0, int(value)))
                elif key == "llm_repetition_penalty":
                    # Float, and 0 is meaningful ("do not send it"), so it
                    # cannot join the max(1, int(...)) group below.
                    value = _clamp_penalty(value)
                elif key in (
                    "llm_timeout_seconds", "max_parallel_workflows",
                    "package_timeout_seconds",
                    "conversation_idle_minutes", "conversation_retention_days",
                    "log_retention_days",
                ):
                    value = max(1, int(value))
            except (TypeError, ValueError):
                if strict:
                    raise
                continue
            setattr(self._settings, key, value)


def _safe_database_url(value: str) -> str:
    """Normalize an env URL, but never fail startup on a bad one.

    Returning it unchanged lets the connection raise a real error naming the
    URL, which is clearer than a crash during settings construction.
    """
    try:
        return normalize_database_url(value)
    except (TypeError, ValueError):
        return value


def _clamp_penalty(value) -> float:
    """0 means "do not send the parameter at all" — the off switch, and the
    default, since OpenAI rejects the key outright. 2.0 is the top of the
    range the servers implementing it accept. Values between 0 and 1 reward
    repetition rather than penalizing it; unusual, but a legitimate ask, so
    they pass through rather than being floored to neutral."""
    return min(2.0, max(0.0, float(value)))


def _safe_schema(value: str) -> str:
    try:
        return normalize_database_schema(value)
    except (TypeError, ValueError):
        return ""
