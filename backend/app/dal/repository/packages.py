"""FLAPI package (tool) persistence.

One row per `package_key`: an FDE edit updates the tool in place rather than
appending a version. `workflow_steps.package_version_id` therefore pins the
tool itself, and a step follows the tool's edits instead of holding an older
copy of it.
"""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug


class PackageRepository:
    def list_packages(self) -> List[dict]:
        return self._all("SELECT * FROM summary_packages ORDER BY name")

    def agent_tools(self) -> List[dict]:
        return self._all("""
            SELECT * FROM summary_packages
            WHERE agent_enabled IS TRUE
            ORDER BY name
        """)

    def agent_tools_by_keys(self, keys: List[str]) -> List[dict]:
        """Enabled standalone tools assigned to one project, in its order."""
        if not keys:
            return []
        rows = self._all("""
            SELECT * FROM summary_packages
            WHERE agent_enabled IS TRUE AND package_key = ANY(%s)
        """, (keys,))
        by_key = {row["package_key"]: row for row in rows}
        return [by_key[key] for key in keys if key in by_key]

    def get_package(self, package_id: str) -> dict:
        return self._one(
            "SELECT * FROM summary_packages WHERE id=%s", (package_id,)
        )

    def create_package(self, data: dict) -> dict:
        package_key = data.get("package_key") or slug(data["name"])
        if self._key_taken("summary_packages", "package_key", package_key):
            raise ValueError(
                "כבר קיים טול במפתח %s. יש לערוך אותו או לבחור שם אחר."
                % package_key
            )
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(_INSERT_PACKAGE, _package_values(
                row_id, package_key, data
            ))
            connection.commit()
        return self.get_package(row_id)

    def update_package(self, package_id: str, data: dict) -> dict:
        """Edit a tool in place.

        `package_key` is the tool's identity and is never rewritten from the
        payload: the workflow steps that point here were wired against this
        key, and renaming it under them would leave them pointing at a tool
        the FDE no longer recognises.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        self.get_package(package_id)
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_PACKAGE, _package_update_values(package_id, data)
            )
            connection.commit()
        return self.get_package(package_id)

    def delete_package(self, package_id: str) -> dict:
        """Remove a tool.

        `workflow_steps.package_version_id` has no `ON DELETE` clause, so a
        tool still wired into a workflow would otherwise fail as a raw
        constraint violation — a 500 with a psycopg message. It is named here
        instead, with the workflows that block it.
        """
        package = self._one(
            "SELECT package_key, name FROM summary_packages WHERE id=%s",
            (package_id,),
        )
        used_by = self._workflows_using(package["package_key"])
        if used_by:
            raise ValueError(
                "אי אפשר למחוק טול שנמצא בשימוש בתהליכים: %s. "
                "יש למחוק או לערוך אותם קודם." % "; ".join(used_by)
            )
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM summary_packages WHERE id=%s", (package_id,)
            )
            connection.commit()
        return {"deleted": package["package_key"], "name": package["name"]}

    def _workflows_using(self, package_key: str) -> List[str]:
        """Names of workflows whose steps point at this tool."""
        rows = self._all("""
            SELECT DISTINCT w.name
            FROM workflow_steps AS s
            JOIN summary_packages AS p ON p.id = s.package_version_id
            JOIN summary_workflows AS w ON w.id = s.workflow_id
            WHERE p.package_key = %s
            ORDER BY w.name
        """, (package_key,))
        return [row["name"] for row in rows]


def _package_fields(data):
    """Every editable column, in the order both statements below use."""
    return (
        data["name"], data.get("description", ""), str(data["package_id"]),
        data["input_cube_name"], data["input_cube_parameter"],
        data.get("input_mode", "single"), data["output_cube_name"],
        data.get("query_name", ""), data.get("timeout_seconds"),
        data.get("agent_enabled", True), data.get("agent_instructions", ""),
        Jsonb(data.get("output_schema", {})),
        Jsonb(data.get("example_input", [])),
        Jsonb(data.get("example_output", [])),
    )


def _package_values(row_id, package_key, data):
    return (row_id, package_key) + _package_fields(data)


def _package_update_values(package_id, data):
    return _package_fields(data) + (package_id,)


_INSERT_PACKAGE = """
    INSERT INTO summary_packages (
        id, package_key, name, description, package_id,
        input_cube_name, input_cube_parameter, input_mode,
        output_cube_name, query_name, timeout_seconds,
        agent_enabled, agent_instructions,
        output_schema, example_input, example_output
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_UPDATE_PACKAGE = """
    UPDATE summary_packages SET
        name=%s, description=%s, package_id=%s,
        input_cube_name=%s, input_cube_parameter=%s, input_mode=%s,
        output_cube_name=%s, query_name=%s, timeout_seconds=%s,
        agent_enabled=%s, agent_instructions=%s,
        output_schema=%s, example_input=%s, example_output=%s
    WHERE id=%s
"""
