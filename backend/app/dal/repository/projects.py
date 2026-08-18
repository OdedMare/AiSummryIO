"""Session-owned project workspaces over the shared capability catalog."""

from typing import List

from psycopg.types.json import Jsonb

from app.common.errors import NotFoundError
from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class ProjectRepository:
    def list_projects(self, session_id: str) -> List[dict]:
        return self._all("""
            SELECT * FROM projects
            WHERE session_id=%s ORDER BY updated_at DESC, created_at DESC
        """, (session_id,))

    def get_project(self, project_id: str, session_id: str) -> dict:
        rows = self._all("""
            SELECT * FROM projects WHERE id=%s AND session_id=%s
        """, (project_id, session_id))
        if not rows:
            raise NotFoundError("הפרויקט לא נמצא")
        return rows[0]

    def create_project(self, session_id: str, data: dict) -> dict:
        self._validate_capabilities(data)
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_PROJECT, _project_values(row_id, session_id, data)
            )
            connection.commit()
        return self.get_project(row_id, session_id)

    def update_project(
        self, project_id: str, session_id: str, data: dict
    ) -> dict:
        self.get_project(project_id, session_id)
        self._validate_capabilities(data)
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_PROJECT, _project_update_values(
                    project_id, session_id, data
                ),
            )
            connection.commit()
        return self.get_project(project_id, session_id)

    def delete_project(self, project_id: str, session_id: str) -> dict:
        project = self.get_project(project_id, session_id)
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM projects WHERE id=%s AND session_id=%s",
                (project_id, session_id),
            )
            connection.commit()
        return {"deleted": project_id, "name": project["name"]}

    def _validate_capabilities(self, data: dict) -> None:
        checks = (
            ("tool_keys", "summary_packages", "package_key", None, "טולים"),
            (
                "workflow_keys", "summary_workflows", "workflow_key", None,
                "Workflows",
            ),
            ("skill_keys", "agent_content", "content_key", "skill", "Skills"),
            ("agent_keys", "agent_content", "content_key", "agent", "סוכנים"),
        )
        for field, table, column, kind, label in checks:
            wanted = data.get(field) or []
            if not wanted:
                continue
            condition = "%s = ANY(%%s)" % column
            params = (wanted,)
            if kind:
                condition += " AND kind=%s"
                params += (kind,)
            rows = self._all(
                "SELECT %s AS key FROM %s WHERE %s" % (
                    column, table, condition,
                ),
                params,
            )
            found = {row["key"] for row in rows}
            missing = [key for key in wanted if key not in found]
            if missing:
                raise ValueError(
                    "%s לא קיימים בקטלוג: %s" % (label, ", ".join(missing))
                )


def _project_fields(data):
    return (
        data["name"], data["mission"],
        Jsonb(data.get("tool_keys", [])),
        Jsonb(data.get("workflow_keys", [])),
        Jsonb(data.get("skill_keys", [])),
        Jsonb(data.get("agent_keys", [])),
    )


def _project_values(row_id, session_id, data):
    return (row_id, session_id) + _project_fields(data)


def _project_update_values(project_id, session_id, data):
    return _project_fields(data) + (project_id, session_id)


_INSERT_PROJECT = """
    INSERT INTO projects (
        id, session_id, name, mission,
        tool_keys, workflow_keys, skill_keys, agent_keys
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
"""

_UPDATE_PROJECT = """
    UPDATE projects SET
        name=%s, mission=%s, tool_keys=%s, workflow_keys=%s,
        skill_keys=%s, agent_keys=%s, updated_at=NOW()
    WHERE id=%s AND session_id=%s
"""
