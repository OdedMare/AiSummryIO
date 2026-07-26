import re

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)
_PG_SCHEMES = ("postgresql://", "postgres://")


def normalize_http_url(value: str, field: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(field + " must start with http:// or https://")
    return cleaned


def normalize_llm_base_url(url: str) -> str:
    """Accept a pasted endpoint, not just the base.

    Users copy the URL they see in a gateway's docs or in another client,
    which usually ends at the operation. The OpenAI SDK appends the path
    itself, so those suffixes must come off or every call 404s.
    """
    cleaned = _strip_suffixes(
        url, ("/chat/completions", "/completions", "/models")
    )
    return normalize_http_url(cleaned, "llm_base_url")


def normalize_database_url(value: str) -> str:
    cleaned = _JDBC_PREFIX.sub("", value.strip())
    if not cleaned.lower().startswith(_PG_SCHEMES):
        raise ValueError(
            "database_url must start with postgresql:// "
            "(jdbc:postgresql://... is accepted and converted automatically)"
        )
    return cleaned


def _strip_suffixes(url: str, suffixes) -> str:
    cleaned = url.strip().rstrip("/")
    suffix = next(
        (item for item in suffixes if cleaned.lower().endswith(item)), None
    )
    return cleaned[:-len(suffix)] if suffix else cleaned

