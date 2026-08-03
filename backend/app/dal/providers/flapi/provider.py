"""FLAPI Flow Package provider using the same flunks seam as LocatoAI.

Run one package, normalize the result, retry once. Nothing else: timeout
policy and credential shaping live in `runner_config`, and translation
to/from flunks models lives in `mapper`.
"""

import logging
import time
from typing import Any, Dict, List

from flunks import FlunksRunner
from flunks.config import FlapiConfig, FlunksConfig

from app.common.errors import ProviderError
from app.dal.providers.flapi.mapper import FlunksMapper
from app.dal.providers.flapi.runner_config import (
    build_flapi_config, resolve_timeout, run_bounded,
)

_ATTEMPTS = 2


class FlapiProvider:
    def __init__(self, settings_store, runner_factory=None):
        self._store = settings_store
        self._mapper = FlunksMapper()
        self._runner_factory = runner_factory
        self._logger = logging.getLogger(__name__)

    def run(self, package: dict, identifiers: List[str]) -> List[dict]:
        """Return the package's rows, retrying once before giving up."""
        last_attempt = _ATTEMPTS - 1
        self._logger.info(
            "FLAPI run package=%s id_count=%d mode=%s timeout=%ss",
            package.get("package_key"), len(identifiers),
            package.get("input_mode"),
            resolve_timeout(package, self._store.get()),
        )
        for attempt in range(_ATTEMPTS):
            try:
                return self._attempt(package, identifiers, attempt)
            except Exception as exc:
                self._logger.warning(
                    "FLAPI attempt %d/%d failed package=%s %s: %s",
                    attempt + 1, _ATTEMPTS, package.get("package_key"),
                    type(exc).__name__, exc,
                )
                if attempt == last_attempt:
                    raise self._failure(package, exc) from exc
        raise AssertionError("unreachable: the last attempt returns or raises")

    def _attempt(
        self, package: dict, identifiers: List[str], attempt: int = 0
    ) -> List[dict]:
        """One full run: configure, execute under a timeout, normalize.

        Each stage is announced before it starts. The whole point is that a
        hang leaves a START line with no matching OK line, which names the
        stage that never returned instead of leaving a silent gap.
        """
        key = package["package_key"]
        self._logger.debug(
            "FLAPI [%s] attempt=%d building package config", key, attempt + 1,
        )
        config = self._mapper.package_config(package, identifiers)
        timeout = resolve_timeout(package, self._store.get())

        self._logger.debug("FLAPI [%s] constructing runner", key)
        runner = self._runner(config)

        self._logger.info(
            "FLAPI [%s] calling flunks .run() (timeout=%ss) — no cancellation, "
            "a hang past this point leaks its worker thread", key, timeout,
        )
        started = time.time()
        result = run_bounded(runner, timeout, key)
        self._logger.info(
            "FLAPI [%s] flunks returned in %.2fs", key, time.time() - started,
        )

        records = self._tag_query(self._mapper.normalize(result), package)
        self._logger.info(
            "FLAPI package OK package=%s rows=%d elapsed=%.2fs",
            key, len(records), time.time() - started,
        )
        if records:
            self._logger.debug(
                "FLAPI [%s] first row keys=%s", key, sorted(records[0].keys()),
            )
        return records

    @staticmethod
    def _tag_query(
        records: List[Dict[str, Any]], package: dict
    ) -> List[Dict[str, Any]]:
        """Stamp each row with the query it came from, for provenance."""
        query_name = package.get("query_name")
        if query_name:
            for record in records:
                record.setdefault("_package_query", query_name)
        return records

    def _failure(self, package: dict, exc: Exception) -> ProviderError:
        """Log the exhausted package and shape the error the caller sees."""
        self._logger.error(
            "FLAPI package FAILED package=%s type=%s",
            package["package_key"], type(exc).__name__,
        )
        return ProviderError("חבילת FLAPI נכשלה: " + str(exc))

    def _runner(self, package_config):
        """The flunks runner for this package: injected one, or a real one."""
        settings = self._store.get()
        self._require_credentials(settings)
        if self._runner_factory:
            return self._runner_factory(settings, package_config)
        return self._flunks_runner(settings, package_config)

    @staticmethod
    def _require_credentials(settings) -> None:
        if not settings.flapi_username or not settings.flapi_token:
            raise ProviderError("יש להגדיר שם משתמש וטוקן FLAPI")

    @staticmethod
    def _flunks_runner(settings, package_config):
        return FlunksRunner(
            flapi_config=build_flapi_config(FlapiConfig, settings),
            package_config=package_config,
            flunks_config=FlunksConfig(),
        )
