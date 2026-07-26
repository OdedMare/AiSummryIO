"""PostgreSQL connection factory driven by live runtime settings."""

import psycopg
from psycopg.rows import dict_row

from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore


def connect(store: RuntimeSettingsStore) -> psycopg.Connection:
    settings = store.get()
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        **_credentials(settings),
    )


def _credentials(settings) -> dict:
    """Explicit fields override whatever the URL carries; empty means
    "not set", so it must not be passed at all."""
    optional = {
        "user": settings.database_user,
        "password": settings.database_password,
        "host": settings.database_host,
        "dbname": settings.database_name,
    }
    credentials = {key: value for key, value in optional.items() if value}
    if settings.database_port is not None:
        credentials["port"] = settings.database_port
    return credentials

