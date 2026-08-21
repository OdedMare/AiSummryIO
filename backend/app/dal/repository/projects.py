"""Session-owned project workspaces over the shared capability catalog."""

from typing import List

from psycopg.types.json import Jsonb

from app.common.errors import ConflictError, NotFoundError
from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class ProjectRepository:
    def list_projects(self, session_id: str) -> List[dict]:
        self._ensure_system_project(session_id)
        return self._with_capabilities(self._all("""
            SELECT * FROM projects
            WHERE session_id=%s
            ORDER BY is_system DESC, updated_at DESC, created_at DESC
        """, (session_id,)))

    def system_project(self, session_id: str) -> dict:
        """The compatibility workspace that owns the pre-project catalog."""
        self._ensure_system_project(session_id)
        return self._with_capabilities(self._all("""
            SELECT * FROM projects
            WHERE session_id=%s AND is_system IS TRUE
            LIMIT 1
        """, (session_id,)))[0]

    def get_project(self, project_id: str, session_id: str) -> dict:
        rows = self._all("""
            SELECT * FROM projects WHERE id=%s AND session_id=%s
        """, (project_id, session_id))
        if not rows:
            raise NotFoundError("הפרויקט לא נמצא")
        return self._with_capabilities(rows)[0]

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
        current = self.get_project(project_id, session_id)
        if current.get("is_system"):
            data = dict(data, name=_SYSTEM_PROJECT_NAME)
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
        if project.get("is_system"):
            raise ConflictError("לא ניתן למחוק את פרויקט המערכת Hunger Games")
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM projects WHERE id=%s AND session_id=%s",
                (project_id, session_id),
            )
            connection.commit()
        return {"deleted": project_id, "name": project["name"]}

    def _ensure_system_project(self, session_id: str) -> None:
        """Create the legacy-data workspace once and attach old threads.

        This runs after startup seeding, so its key lists are a snapshot of
        every capability the installation had before project selection was
        introduced. The partial unique index makes concurrent first loads
        idempotent without rewriting any catalog row.
        """
        with connect(self._store) as connection:
            connection.execute(_INSERT_SYSTEM_PROJECT, (
                new_id(), session_id, _SYSTEM_PROJECT_NAME,
                _SYSTEM_PROJECT_MISSION, session_id,
            ))
            connection.execute("""
                UPDATE conversations AS conversation
                SET project_id = project.id
                FROM projects AS project
                WHERE project.session_id=%s AND project.is_system IS TRUE
                  AND conversation.session_id=%s
                  AND conversation.project_id IS NULL
            """, (session_id, session_id))
            project = connection.execute("""
                SELECT id FROM projects
                WHERE session_id=%s AND is_system IS TRUE LIMIT 1
            """, (session_id,)).fetchone()
            if project:
                for table in (
                    "summary_packages", "summary_workflows", "agent_content"
                ):
                    connection.execute(
                        "UPDATE %s SET project_id=%%s WHERE project_id IS NULL"
                        % table,
                        (project["id"],),
                    )
            connection.commit()

    def _with_capabilities(self, rows: List[dict]) -> List[dict]:
        """Project keys are a projection of rows it owns, never shared state."""
        for row in rows:
            project_id = row["id"]
            row["tool_keys"] = self._keys_for(
                "summary_packages", "package_key", project_id
            )
            row["workflow_keys"] = self._keys_for(
                "summary_workflows", "workflow_key", project_id
            )
            row["skill_keys"] = self._content_keys(project_id, "skill")
            row["agent_keys"] = self._content_keys(project_id, "agent")
        return rows

    def _keys_for(self, table: str, column: str, project_id: str) -> List[str]:
        rows = self._all(
            "SELECT %s AS key FROM %s WHERE project_id=%%s ORDER BY name"
            % (column, table),
            (project_id,),
        )
        return [item["key"] for item in rows]

    def _content_keys(self, project_id: str, kind: str) -> List[str]:
        rows = self._all("""
            SELECT content_key AS key FROM agent_content
            WHERE project_id=%s AND kind=%s ORDER BY name
        """, (project_id, kind))
        return [item["key"] for item in rows]

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


_SYSTEM_PROJECT_NAME = "Hunger Games"
_SYSTEM_PROJECT_MISSION = (
    "סביבת העבודה הקיימת, עם כל הטולים, ה-Workflows, ה-Skills והסוכנים "
    "שהיו במערכת לפני הוספת פרויקטים."
)

_INSERT_SYSTEM_PROJECT = """
    INSERT INTO projects (
        id, session_id, name, mission, tool_keys, workflow_keys,
        skill_keys, agent_keys, is_system
    )
    SELECT
        %s, %s, %s, %s,
        COALESCE((
            SELECT jsonb_agg(package_key ORDER BY name)
            FROM summary_packages
        ), '[]'::jsonb),
        COALESCE((
            SELECT jsonb_agg(workflow_key ORDER BY name)
            FROM summary_workflows
        ), '[]'::jsonb),
        COALESCE((
            SELECT jsonb_agg(content_key ORDER BY name)
            FROM agent_content WHERE kind='skill'
        ), '[]'::jsonb),
        COALESCE((
            SELECT jsonb_agg(content_key ORDER BY name)
            FROM agent_content WHERE kind='agent'
        ), '[]'::jsonb),
        TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM projects WHERE session_id=%s AND is_system IS TRUE
    )
    ON CONFLICT DO NOTHING
"""
