"""Environment defaults; UI overrides are applied by RuntimeSettingsStore."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env-derived DEFAULTS. Values the user can edit in the UI live in
    common.runtime_settings (this feeds its initial values)."""

    model_config = SettingsConfigDict(
        env_prefix="AISUMMRY_", env_file=".env", extra="ignore"
    )

    database_url: str = (
        "postgresql://spear:spear@rnd619-nv-prd01:5432/spear"
    )
    """Postgres holding conversations, workflows, and evidence. A
    `jdbc:postgresql://...` URL is accepted and converted automatically."""

    database_user: str = "spear"
    """Optional explicit Postgres user. Overrides credentials in the URL."""

    database_password: str = ""
    """Optional explicit Postgres password. Never returned by the API."""

    database_host: str = "rnd619-nv-prd01"
    """Optional explicit Postgres host. Overrides the host in the URL."""

    database_port: Optional[int] = 5432
    """Optional explicit Postgres port. Overrides the port in the URL."""

    database_name: str = "spear"
    """Optional explicit database name. Overrides the database in the URL."""

    database_schema: str = "sumorai"
    """PostgreSQL schema owning every table. Empty means the server default
    (normally `public`). Also settable as `?currentSchema=` in the URL."""

    llm_model: str = "gemma4:31b-it"
    """The main model — Gemma 4 31B served through Ollama."""

    llm_diet_mode: bool = False
    """Use compact prompts, schema samples, and bounded completion output."""

    llm_timeout_seconds: int = 120
    """Maximum wall time for ONE HTTP completion to the model.

    Not a budget for the whole logical call: the degradation ladder and the
    parse retry above it each get their own, so a pathological call can take
    a multiple of this. It exists to stop a hung model server from holding a
    worker for the SDK's 600-second default."""

    llm_repetition_penalty: float = 0.0
    """Penalty applied to already-emitted tokens, discouraging loops.

    NOT a standard OpenAI field — it is a vLLM/Ollama/TGI extension, so it is
    sent inside `extra_body`. `0` means "do not send it at all" and is the
    default, because OpenAI itself rejects the unknown key; `1.0` is neutral
    on the servers that do implement it, and above that penalizes. Past ~1.2
    it starts to fight JSON mode, since the syntax a JSON object must repeat
    (braces, quotes, commas) is exactly what the penalty suppresses."""

    llm_base_url: Optional[str] = "http://localhost:11434/v1"
    """OpenAI-compatible endpoint. Default: local Ollama. From inside the
    backend container use http://pghost:11434/v1 (see runtime-settings)."""

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")

    flapi_username: Optional[str] = "665avivs"
    flapi_token: str = ""
    flapi_verify_tls: bool = True

    max_parallel_workflows: int = 4
    agent_max_rounds: int = 1
    package_timeout_seconds: int = 120
    conversation_idle_minutes: int = 60
    conversation_retention_days: int = 30
    log_retention_days: int = 90

    cookie_secret: str = ""

    runtime_settings_file: str = "runtime-settings.json"
    request_log_path: str = "logs/requests.jsonl"
