"""PostgreSQL connection factory driven by live runtime settings."""

import psycopg
from psycopg.rows import dict_row


def connect(store):
    settings = store.get()
    optional = {
        "user": settings.database_user,
        "password": settings.database_password,
        "host": settings.database_host,
        "dbname": settings.database_name,
    }
    credentials = {key: value for key, value in optional.items() if value}
    if settings.database_port is not None:
        credentials["port"] = settings.database_port
    return psycopg.connect(
        settings.database_url, row_factory=dict_row, **credentials
    )

