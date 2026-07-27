"""Versioned FLAPI package persistence."""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug


class PackageRepository:
    def list_packages(self) -> List[dict]:
        return self._all("""
            SELECT DISTINCT ON (package_key) *
            FROM summary_packages
            ORDER BY package_key, version DESC
        """)

    def agent_tools(self) -> List[dict]:
        return self._all("""
            SELECT * FROM (
                SELECT DISTINCT ON (package_key) *
                FROM summary_packages
                ORDER BY package_key, version DESC
            ) AS latest
            WHERE agent_enabled IS TRUE
            ORDER BY name
        """)

    def get_package(self, version_id: str) -> dict:
        return self._one(
            "SELECT * FROM summary_packages WHERE id=%s", (version_id,)
        )

    def create_package(self, data: dict) -> dict:
        package_key = data.get("package_key") or slug(data["name"])
        version = self._next_version(
            "summary_packages", "package_key", package_key
        )
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(_INSERT_PACKAGE, _package_values(
                row_id, package_key, version, data
            ))
            connection.commit()
        return self.get_package(row_id)


def _package_values(row_id, package_key, version, data):
    return (
        row_id, package_key, version, data["name"],
        data.get("description", ""), str(data["package_id"]),
        data["input_cube_name"], data["input_cube_parameter"],
        data.get("input_mode", "single"), data.get("input_kind", "both"),
        data["output_cube_name"],
        data.get("query_name", ""), data.get("timeout_seconds"),
        data.get("agent_enabled", True), data.get("agent_instructions", ""),
        Jsonb(data.get("output_schema", {})),
        Jsonb(data.get("example_input", [])),
        Jsonb(data.get("example_output", [])),
    )


_INSERT_PACKAGE = """
    INSERT INTO summary_packages (
        id, package_key, version, name, description, package_id,
        input_cube_name, input_cube_parameter, input_mode, input_kind,
        output_cube_name, query_name, timeout_seconds,
        agent_enabled, agent_instructions,
        output_schema, example_input, example_output
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""
