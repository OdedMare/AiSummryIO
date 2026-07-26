"""FLAPI Flow Package provider using the same flunks seam as LocatoAI."""

import logging
from typing import List

from app.common.errors import ProviderError
from app.dal.providers.flapi.mapper import FlunksMapper


class FlapiProvider:
    def __init__(self, settings_store, runner_factory=None):
        self._store = settings_store
        self._mapper = FlunksMapper()
        self._runner_factory = runner_factory
        self._logger = logging.getLogger(__name__)

    def run(self, package: dict, identifiers: List[str]) -> List[dict]:
        config = self._mapper.package_config(package, identifiers)
        runner = self._runner(config)
        for attempt in range(2):
            try:
                result = runner.run()
                records = self._mapper.normalize(result)
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
            flapi_config=FlApiConfig(
                username=settings.flapi_username,
                token=settings.flapi_token,
            ),
            package_config=package_config,
            flunks_config=FlunksConfig(),
        )

