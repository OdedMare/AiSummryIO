"""Bounded retry for transient OpenAI-compatible failures."""

import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError)


def create_with_retry(client, model: str, kwargs: dict):
    last_error = None
    for attempt in range(2):
        try:
            return client.chat.completions.create(
                model=model, temperature=0, **kwargs
            )
        except _ERRORS as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.3)
    raise last_error

