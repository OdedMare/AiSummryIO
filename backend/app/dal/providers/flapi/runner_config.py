"""Timeout policy and flunks credential config, kept out of the provider.

The provider's job is to run a package and normalize the result. Deciding how
long a package may run, and shaping credentials for whichever flunks version
is installed, are separate concerns that change for different reasons.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.common.errors import ProviderError
from app.common.logging_setup import record_abandoned_worker

_DEFAULT_TIMEOUT_SECONDS = 120

# Names used by different flunks versions for the same TLS-verification flag.
_TLS_FIELDS = ("verify_tls", "verify", "verify_ssl")

_logger = logging.getLogger(__name__)


def resolve_timeout(package: dict, settings) -> int:
    """Per-package timeout, falling back to the global setting."""
    configured = package.get("timeout_seconds")
    if configured is None:
        configured = getattr(
            settings, "package_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS
        )
    return max(1, int(configured))


def run_bounded(runner, timeout: int, package_key: str):
    """Run `runner.run()` but wait no longer than `timeout` seconds.

    flunks exposes no cancellation, so the worker thread may outlive the
    timeout. Bounding the wait is what keeps one slow package from stalling
    the whole run.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    started = time.time()
    try:
        future = pool.submit(runner.run)
        try:
            result = future.result(timeout=timeout)
            _logger.debug(
                "run_bounded [%s] completed in %.2fs",
                package_key, time.time() - started,
            )
            return result
        except FutureTimeoutError:
            _record_abandoned(package_key, timeout, future)
            raise ProviderError(
                "חבילת FLAPI חרגה מזמן הריצה (%d שניות): %s"
                % (timeout, package_key)
            )
    finally:
        pool.shutdown(wait=False)


def _record_abandoned(package_key: str, timeout: int, future) -> None:
    """Announce a thread that timed out and can never be reclaimed.

    ``shutdown(wait=False)`` returns immediately but the worker keeps running
    inside flunks, holding its slot forever. Each of these permanently
    subtracts one worker from the pool that serves runs, so the count is the
    number that matters when the queue later wedges: once it reaches the pool
    size, nothing new can ever start.
    """
    total = record_abandoned_worker()
    _logger.error(
        "run_bounded [%s] TIMEOUT after %ds — worker thread ABANDONED "
        "(flunks cannot be cancelled). abandoned_total=%d live_threads=%d",
        package_key, timeout, total, threading.active_count(),
    )
    future.add_done_callback(
        lambda done: _logger.warning(
            "run_bounded [%s] abandoned worker finally finished after the "
            "timeout; its result is discarded (cancelled=%s)",
            package_key, done.cancelled(),
        )
    )


def build_flapi_config(config_class, settings):
    """Build FlapiConfig, passing verify_tls only if this version accepts it.

    The internal flunks version may predate the field, so an older wheel keeps
    working instead of failing on an unexpected keyword argument.
    """
    values = {
        "username": settings.flapi_username,
        "token": settings.flapi_token,
    }
    for field in _TLS_FIELDS:
        if _accepts(config_class, field):
            values[field] = settings.flapi_verify_tls
            break
    else:
        if not settings.flapi_verify_tls:
            _logger.warning(
                "flapi_verify_tls=False requested but this flunks version "
                "exposes no TLS-verification field; the setting is ignored."
            )
    return config_class(**values)


def _accepts(config_class, field: str) -> bool:
    fields = getattr(config_class, "model_fields", None)
    if isinstance(fields, dict):
        return field in fields
    fields = getattr(config_class, "__fields__", None)
    if isinstance(fields, dict):
        return field in fields
    annotations = getattr(config_class, "__annotations__", None)
    return bool(annotations) and field in annotations
