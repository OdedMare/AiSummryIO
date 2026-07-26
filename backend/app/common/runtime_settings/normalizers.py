import re

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)


def normalize_http_url(value: str, field: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(field + " must start with http:// or https://")
    return cleaned


def normalize_database_url(value: str) -> str:
    cleaned = _JDBC_PREFIX.sub("", value.strip())
    if not cleaned.lower().startswith(("postgresql://", "postgres://")):
        raise ValueError("database_url must start with postgresql://")
    return cleaned

