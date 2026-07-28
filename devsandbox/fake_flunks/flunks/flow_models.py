"""Stand-in for `flunks.flow_models`."""

from typing import Any, List


class PackageInputCube:
    def __init__(
        self,
        cube_name: str = "",
        cube_parameter: str = "",
        values: List[Any] = None,
        **extra
    ):
        self.cube_name = cube_name
        self.cube_parameter = cube_parameter
        self.values = list(values or [])
        self.__dict__.update(extra)


class PackageOutputCube:
    def __init__(self, cube_name: str = "", **extra):
        self.cube_name = cube_name
        self.__dict__.update(extra)
