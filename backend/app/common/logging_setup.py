"""Console logging configuration.

Nothing configured the root logger before this module, so every
``logger.info`` in the codebase was written to a handler that did not exist
and silently dropped. Uvicorn configures only its own loggers, which is why
request lines appeared while the provider's own tracing never did.

Verbosity is driven by ``AISUMMRY_LOG_LEVEL`` (default ``INFO``); set
``DEBUG`` to include the per-row and per-payload tracing used when
diagnosing a stuck package.
"""

import logging
import os
import sys
import threading
import time

_CONFIGURED = False
_LOCK = threading.Lock()

# Thread name is deliberately part of the line: package execution fans out
# across pools, and "which worker is stuck" is unanswerable without it.
_FORMAT = "%(asctime)s %(levelname)-5s [%(threadName)s] %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"


def configure_logging() -> None:
    """Attach one stdout handler to the root logger, exactly once."""
    global _CONFIGURED
    with _LOCK:
        if _CONFIGURED:
            return
        _CONFIGURED = True

    level = os.getenv("AISUMMRY_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.addHandler(handler)

    # These two are noisy at DEBUG and say nothing about our own behavior.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger("aisummry.boot").info(
        "logging configured level=%s (set AISUMMRY_LOG_LEVEL=DEBUG for more)",
        level,
    )


def trace(name: str) -> logging.Logger:
    """A logger under the shared ``aisummry`` prefix."""
    return logging.getLogger("aisummry." + name)


class Timed:
    """Log how long a block took, and whether it raised.

    Used around every external call, because the symptom being chased is a
    call that never returns: a start line with no matching end line is what
    identifies the hung stage.
    """

    def __init__(self, logger: logging.Logger, label: str, **context):
        self._logger = logger
        self._label = label
        self._context = context
        self._started = 0.0

    def __enter__(self):
        self._started = time.time()
        self._logger.info("START %s%s", self._label, _suffix(self._context))
        return self

    def __exit__(self, exc_type, exc, _traceback):
        elapsed = time.time() - self._started
        if exc_type is None:
            self._logger.info(
                "OK    %s (%.2fs)%s", self._label, elapsed,
                _suffix(self._context),
            )
            return False
        self._logger.error(
            "FAIL  %s (%.2fs) %s: %s%s", self._label, elapsed,
            exc_type.__name__, exc, _suffix(self._context),
        )
        return False


def _suffix(context: dict) -> str:
    if not context:
        return ""
    return " " + " ".join(
        "%s=%s" % (key, value) for key, value in sorted(context.items())
    )


# Worker threads permanently lost to FLAPI timeouts, process-wide.
#
# The counter lives here rather than beside the provider because both layers
# need it — `dal/` increments it, `bl/`'s watchdog reports it — and routing
# that through `common/` avoids importing the flunks-dependent provider into
# the job queue, which must stay importable without the wheel.
_abandoned = 0
_abandoned_lock = threading.Lock()


def record_abandoned_worker() -> int:
    global _abandoned
    with _abandoned_lock:
        _abandoned += 1
        return _abandoned


def abandoned_workers() -> int:
    with _abandoned_lock:
        return _abandoned
