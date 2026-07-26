"""Translate summary package definitions to/from flunks models."""

from typing import Any, Dict, List

import pandas as pd

from app.common.errors import ProviderError


class FlunksMapper:
    def package_config(self, package: dict, identifiers: List[str]):
        try:
            from flunks.config import FlunksPackageConfig
            from flunks.flow_models import PackageInputCube, PackageOutputCube
        except ImportError as exc:
            raise ProviderError(
                "flunks אינו מותקן. יש להוסיף אותו ל-wheelhouse הפנימי."
            ) from exc
        values = [str(value) for value in identifiers if str(value).strip()]
        if not values:
            raise ProviderError("נדרש לפחות מזהה קלט אחד")
        cube = PackageInputCube(
            cube_name=package["input_cube_name"],
            cube_parameter=package["input_cube_parameter"],
            values=values,
        )
        return FlunksPackageConfig(
            package_id=str(package["package_id"]),
            package_name="",
            main_input_cube=cube,
            output_cube=PackageOutputCube(
                cube_name=package["output_cube_name"]
            ),
        )

    def normalize(self, result: Any) -> List[Dict[str, Any]]:
        if not hasattr(result, "to_dict") or not hasattr(result, "columns"):
            raise ProviderError(
                "flunks החזיר %s במקום DataFrame" % type(result).__name__
            )
        self._reject_duplicate_columns(result)
        return [
            {str(key): self._value(value) for key, value in row.items()}
            for row in result.to_dict("records")
        ]

    @staticmethod
    def _reject_duplicate_columns(result: Any) -> None:
        """``to_dict('records')`` keeps only the last of each duplicate name.

        flunks joins cubes, so two cubes contributing the same column name is
        reachable. Dropping one silently would make the summary incomplete
        with no warning, so this fails loudly instead.
        """
        columns = [str(column) for column in result.columns]
        duplicates = sorted({
            column for column in columns if columns.count(column) > 1
        })
        if duplicates:
            raise ProviderError(
                "flunks החזיר עמודות כפולות: %s" % ", ".join(duplicates)
            )

    @staticmethod
    def _value(value: Any) -> Any:
        if value is None:
            return None
        try:
            if pd.api.types.is_scalar(value) and bool(pd.isna(value)):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(value, "wkt"):
            return value.wkt
        # Temporal values must be checked before ``.item()``: pd.Timestamp
        # exposes ``item()`` but it returns another Timestamp, which psycopg's
        # Jsonb cannot serialize — the evidence write for the whole step would
        # fail, not just this cell.
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "item"):
            return value.item()
        return value

