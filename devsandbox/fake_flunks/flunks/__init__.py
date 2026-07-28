"""Local stand-in for the internal `flunks` FLAPI client.

FOR LOCAL DEVELOPMENT ONLY — this package exists so the app can be exercised
end to end on a machine that has no access to the real FLAPI platform. It is
installed only inside the sandbox container and is never part of the backend
image.

The contract it honours is exactly the one the provider relies on:

- `FlunksRunner(flapi_config=, package_config=, flunks_config=)`
- `.run()` returns a **pandas DataFrame** (never a list of dicts — the mapper
  rejects anything without `.columns` / `.to_dict`)

Rows come from `mock_data.rows_for`, keyed by the package's `package_id`.

Two behaviours make the mock useful rather than merely non-failing:

- `FLUNKS_MOCK_LATENCY_SECONDS` adds a delay, so progressive rendering and the
  per-package timeout are actually observable.
- `FLUNKS_MOCK_FAIL_PACKAGES` (comma-separated `package_id`s) makes a package
  raise, to exercise partial success — the app's rule that a failed package
  never discards successful sections.
"""

import logging
import os
import time
from typing import List

import pandas as pd

from flunks.config import FlapiConfig, FlunksConfig, FlunksPackageConfig
from flunks.flow_models import PackageInputCube, PackageOutputCube
from flunks.mock_data import rows_for

__all__ = [
    "FlunksRunner", "FlapiConfig", "FlunksConfig", "FlunksPackageConfig",
    "PackageInputCube", "PackageOutputCube",
]

_logger = logging.getLogger(__name__)


def _failing_packages() -> List[str]:
    raw = os.environ.get("FLUNKS_MOCK_FAIL_PACKAGES", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _latency() -> float:
    try:
        return float(os.environ.get("FLUNKS_MOCK_LATENCY_SECONDS", "0"))
    except ValueError:
        return 0.0


class MockFlapiError(RuntimeError):
    """What the real client would raise on a platform-side failure."""


class FlunksRunner:
    def __init__(
        self, flapi_config=None, package_config=None, flunks_config=None
    ):
        self.flapi_config = flapi_config
        self.package_config = package_config
        self.flunks_config = flunks_config

    def run(self) -> pd.DataFrame:
        package_id = str(getattr(self.package_config, "package_id", ""))
        identifiers = self._identifiers()

        latency = _latency()
        if latency:
            time.sleep(latency)

        if package_id in _failing_packages():
            raise MockFlapiError(
                "mock: package %s is configured to fail" % package_id
            )

        rows = rows_for(package_id, identifiers)
        _logger.info(
            "mock flunks package=%s inputs=%d rows=%d",
            package_id, len(identifiers), len(rows),
        )
        # An empty result must still carry the column names, so a package
        # that legitimately finds nothing looks different from a broken one.
        return pd.DataFrame(rows)

    def _identifiers(self) -> List[str]:
        cube = getattr(self.package_config, "main_input_cube", None)
        return [str(value) for value in getattr(cube, "values", []) or []]
