"""Stand-in for `flunks.config`.

Permissive attribute bags. `FlapiConfig` deliberately declares `verify_tls`
in `__annotations__` so `build_flapi_config` finds a TLS field the same way
it would against the real library.
"""

from typing import Any, List, Optional


class FlapiConfig:
    username: Optional[str]
    token: Optional[str]
    verify_tls: bool

    def __init__(self, username=None, token=None, verify_tls=True, **extra):
        self.username = username
        self.token = token
        self.verify_tls = verify_tls
        self.__dict__.update(extra)


class FlunksConfig:
    def __init__(self, **extra):
        self.__dict__.update(extra)


class FlunksPackageConfig:
    def __init__(
        self,
        package_id: str = "",
        package_name: str = "",
        main_input_cube: Any = None,
        output_cube: Any = None,
        **extra
    ):
        self.package_id = package_id
        self.package_name = package_name
        self.main_input_cube = main_input_cube
        self.output_cube = output_cube
        self.__dict__.update(extra)

    @property
    def values(self) -> List[str]:
        cube = self.main_input_cube
        return list(getattr(cube, "values", []) or [])
