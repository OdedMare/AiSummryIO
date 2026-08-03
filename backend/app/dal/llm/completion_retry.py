"""Bounded retry for transient OpenAI-compatible failures."""

import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError)
_ATTEMPTS = 2
_DELAY_SECONDS = 0.3
# Deterministic output — the agent emits structured JSON, not prose.
_TEMPERATURE = 0


def create_with_retry(client, model: str, kwargs: dict, deadline=None):
    last_error = None
    for attempt in range(_ATTEMPTS):
        timeout = _remaining(deadline)
        try:
            return client.chat.completions.create(
                model=model, temperature=_TEMPERATURE, timeout=timeout,
                **kwargs
            )
        except _ERRORS as exc:
            last_error = exc
            if attempt + 1 < _ATTEMPTS:
                remaining = _remaining(deadline)
                time.sleep(
                    _DELAY_SECONDS if remaining is None
                    else min(_DELAY_SECONDS, remaining)
                )
    raise last_error


def _remaining(deadline):
    """Seconds left in the logical call, not a fresh timeout per retry."""
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("זמן ההמתנה למודל הסתיים")
    return remaining
