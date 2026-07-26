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

    database_url: str = "postgresql://localhost:5432/summaries"
    """Postgres holding conversations, workflows, and evidence."""

    database_user: str = ""
    """Optional explicit Postgres user. Overrides credentials in the URL."""

    database_password: str = ""
    """Optional explicit Postgres password. Never returned by the API."""

    database_host: str = ""
    """Optional explicit Postgres host. Overrides the host in the URL."""

    database_port: Optional[int] = None
    """Optional explicit Postgres port. Overrides the port in the URL."""

    database_name: str = ""
    """Optional explicit database name. Overrides the database in the URL."""

    llm_model: str = "gemma4:31b-cloud"
    """The main model — Gemma 4 31B served through Ollama."""

    llm_diet_mode: bool = True
    """Use compact prompts, schema samples, and bounded completion output."""

    llm_base_url: Optional[str] = "http://localhost:11434/v1"
    """OpenAI-compatible endpoint. Default: local Ollama. From inside the
    backend container use http://pghost:11434/v1 (see runtime-settings)."""

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")

    flapi_username: Optional[str] = None
    flapi_token: str = ""
    flapi_verify_tls: bool = True

    max_parallel_workflows: int = 4
    package_timeout_seconds: int = 120
    conversation_retention_days: int = 30
    log_retention_days: int = 90

    admin_password: str = ""
    admin_password_hash: str = ""
    cookie_secret: str = ""
    runtime_settings_file: str = "runtime-settings.json"
    request_log_path: str = "logs/requests.jsonl"

