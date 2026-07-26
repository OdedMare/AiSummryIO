"""FLAPI Flow Package provider using the same flunks seam as LocatoAI."""

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
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
        timeout = self._timeout(package)
        for attempt in range(2):
            try:
                runner = self._runner(config)
                result = self._run_with_timeout(runner, timeout, package)
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

    def _timeout(self, package: dict) -> int:
        configured = package.get("timeout_seconds")
        if configured is None:
            configured = getattr(
                self._store.get(), "package_timeout_seconds", 120
            )
        return max(1, int(configured))

    def _run_with_timeout(self, runner, timeout: int, package: dict):
        # flunks exposes no cancellation, so the worker thread may outlive the
        # timeout. Bounding the wait is what keeps one slow package from
        # stalling the whole run.
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(runner.run)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError:
                raise ProviderError(
                    "חבילת FLAPI חרגה מזמן הריצה (%d שניות): %s"
                    % (timeout, package["package_key"])
                )
        finally:
            pool.shutdown(wait=False)

    def _runner(self, package_config):
        settings = self._store.get()
        if not settings.flapi_username or not settings.flapi_token:
            raise ProviderError("יש להגדיר שם משתמש וטוקן FLAPI")
        if self._runner_factory:
            return self._runner_factory(settings, package_config)
        try:
            from flunks import FlunksRunner
            from flunks.config import FlapiConfig, FlunksConfig
        except ImportError as exc:
            raise ProviderError(
                "flunks אינו מותקן. יש להוסיף אותו ל-wheelhouse הפנימי."
            ) from exc
        return FlunksRunner(
            flapi_config=self._flapi_config(FlapiConfig, settings),
            package_config=package_config,
            flunks_config=FlunksConfig(),
        )

    def _flapi_config(self, config_class, settings):
        # verify_tls is an operator-facing setting, but the internal flunks
        # version may predate the field. Only pass what the model accepts so an
        # older wheel keeps working instead of failing on an unexpected kwarg.
        values = {
            "username": settings.flapi_username,
            "token": settings.flapi_token,
        }
        for field in ("verify_tls", "verify", "verify_ssl"):
            if self._accepts(config_class, field):
                values[field] = settings.flapi_verify_tls
                break
        else:
            if not settings.flapi_verify_tls:
                self._logger.warning(
                    "flapi_verify_tls=False requested but this flunks version "
                    "exposes no TLS-verification field; the setting is ignored."
                )
        return config_class(**values)

    @staticmethod
    def _accepts(config_class, field: str) -> bool:
        fields = getattr(config_class, "model_fields", None)
        if isinstance(fields, dict):
            return field in fields
        fields = getattr(config_class, "__fields__", None)
        if isinstance(fields, dict):
            return field in fields
        annotations = getattr(config_class, "__annotations__", None)
        return bool(annotations) and field in annotations
