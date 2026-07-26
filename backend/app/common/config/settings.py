"""Environment defaults; UI overrides are applied by RuntimeSettingsStore."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AISUMMRY_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql://localhost:5432/summaries"
    database_user: str = ""
    database_password: str = ""
    database_host: str = ""
    database_port: Optional[int] = None
    database_name: str = ""

    llm_model: str = "gemma4:31b-cloud"
    llm_diet_mode: bool = True
    llm_base_url: Optional[str] = "http://localhost:11434/v1"
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

