"""Make `flunks` importable during tests.

`flunks` is the internal FLAPI runtime: it is not on the public index and is
not installed in CI, but the provider and mapper now import it at module level
like any other library. Stubs must therefore be in `sys.modules` *before* those
modules are imported, which is why this lives in `conftest.py` rather than in a
fixture — pytest imports it before collecting any test.

Every flunks model becomes a permissive attribute bag, so a test can assert on
whatever was passed without the real library being present. When `flunks` is
genuinely installed, it is left alone.
"""

import sys
from types import ModuleType


class _Model:
    def __init__(self, **values):
        self.__dict__.update(values)


def _install_flunks_stubs():
    root = ModuleType("flunks")
    config = ModuleType("flunks.config")
    flow_models = ModuleType("flunks.flow_models")

    root.FlunksRunner = _Model
    config.FlapiConfig = _Model
    config.FlunksConfig = _Model
    config.FlunksPackageConfig = _Model
    flow_models.PackageInputCube = _Model
    flow_models.PackageOutputCube = _Model

    sys.modules.setdefault("flunks", root)
    sys.modules.setdefault("flunks.config", config)
    sys.modules.setdefault("flunks.flow_models", flow_models)


try:
    import flunks  # noqa: F401
except ImportError:
    _install_flunks_stubs()
