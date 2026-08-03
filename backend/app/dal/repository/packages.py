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

    def delete_package(self, version_id: str) -> dict:
        """Remove a tool and every version of it.

        Deleting one version would leave the catalog showing an older one and
        read as a failed delete, since the list is `DISTINCT ON (package_key)`.
        The whole key goes, which is also what makes the version counter
        restart cleanly if the FDE recreates the tool.

        `workflow_steps.package_version_id` has no `ON DELETE` clause, so a
        tool still wired into a workflow would otherwise fail as a raw
        constraint violation — a 500 with a psycopg message. It is named here
        instead, with the workflows that block it.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        package = self._one(
            "SELECT package_key, name FROM summary_packages WHERE id=%s",
            (version_id,),
        )
        used_by = self._workflows_using(package["package_key"])
        if used_by:
            raise ValueError(
                "אי אפשר למחוק טול שנמצא בשימוש בתהליכים: %s. "
                "יש למחוק או לערוך אותם קודם." % "; ".join(used_by)
            )
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM summary_packages WHERE package_key=%s",
                (package["package_key"],),
            )
            connection.commit()
        return {"deleted": package["package_key"], "name": package["name"]}

    def _workflows_using(self, package_key: str) -> List[str]:
        """Names of workflows whose steps point at any version of this tool."""
        rows = self._all("""
            SELECT DISTINCT w.name, w.version
            FROM workflow_steps AS s
            JOIN summary_packages AS p ON p.id = s.package_version_id
            JOIN summary_workflows AS w ON w.id = s.workflow_id
            WHERE p.package_key = %s
            ORDER BY w.name
        """, (package_key,))
        return ["%s (v%s)" % (row["name"], row["version"]) for row in rows]


def _package_values(row_id, package_key, version, data):
    return (
        row_id, package_key, version, data["name"],
        data.get("description", ""), str(data["package_id"]),
        data["input_cube_name"], data["input_cube_parameter"],
        data.get("input_mode", "single"), data["output_cube_name"],
        data.get("query_name", ""), data.get("timeout_seconds"),
        data.get("agent_enabled", True), data.get("agent_instructions", ""),
        Jsonb(data.get("output_schema", {})),
        Jsonb(data.get("example_input", [])),
        Jsonb(data.get("example_output", [])),
    )


_INSERT_PACKAGE = """
    INSERT INTO summary_packages (
        id, package_key, version, name, description, package_id,
        input_cube_name, input_cube_parameter, input_mode,
        output_cube_name, query_name, timeout_seconds,
        agent_enabled, agent_instructions,
        output_schema, example_input, example_output
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""
