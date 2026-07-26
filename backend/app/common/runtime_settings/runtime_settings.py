from dataclasses import dataclass
from typing import Optional


@dataclass
class RuntimeSettings:
    database_url: str
    database_user: str
    database_password: str
    database_host: str
    database_port: Optional[int]
    database_name: str
    database_schema: str
    llm_model: str
    llm_diet_mode: bool
    llm_base_url: Optional[str]
    openai_api_key: str
    flapi_username: Optional[str]
    flapi_token: str
    flapi_verify_tls: bool
    max_parallel_workflows: int
    package_timeout_seconds: int
    conversation_retention_days: int
    log_retention_days: int
    admin_password_hash: str
    cookie_secret: str

