"""FLAPI Flow Package provider using the same flunks seam as LocatoAI."""

import logging
from typing import List

from app.common.errors import ProviderError
from app.dal.providers.flapi.mapper import FlunksMapper
from app.dal.providers.flapi.runner_config import (
    build_flapi_config, resolve_timeout, run_bounded,
)


class FlapiProvider:
    def __init__(self, settings_store, runner_factory=None):
        self._store = settings_store
        self._mapper = FlunksMapper()
        self._runner_factory = runner_factory
        self._logger = logging.getLogger(__name__)

    def run(self, package: dict, identifiers: List[str]) -> List[dict]:
        config = self._mapper.package_config(package, identifiers)
        timeout = resolve_timeout(package, self._store.get())
        for attempt in range(2):
            try:
                runner = self._runner(config)
                result = run_bounded(runner, timeout, package["package_key"])
                records = self._mapper.normalize(result)
                if package.get("query_name"):
                    for record in records:
                        record.setdefault(
                            "_package_query", package["query_name"]
                        )
                self._logger.info(
                    "FLAPI package OK package=%s rows=%d",
                    package["package_key"], len(records),
                )
                return records
            except Exception as exc:
                if attempt == 1:
                    self._logger.error(
                        "FLAPI package FAILED package=%s type=%s",
                        package["package_key"], type(exc).__name__,
                    )
                    raise ProviderError(
                        "חבילת FLAPI נכשלה: " + str(exc)
                    ) from exc
        return []

    def _runner(self, package_config):
        settings = self._store.get()
        if not settings.flapi_username or not settings.flapi_token:
            raise ProviderError("יש להגדיר שם משתמש וטוקן FLAPI")
        if self._runner_factory:
            return self._runner_factory(settings, package_config)
        try:
            from flunks import FlunksRunner
            from flunks.config import FlApiConfig, FlunksConfig
        except ImportError as exc:
            raise ProviderError(
                "flunks אינו מותקן. יש להוסיף אותו ל-wheelhouse הפנימי."
            ) from exc
        return FlunksRunner(
            flapi_config=build_flapi_config(FlApiConfig, settings),
            package_config=package_config,
            flunks_config=FlunksConfig(),
        )
