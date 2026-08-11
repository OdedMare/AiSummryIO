"""Workflow and step persistence.

One row per `workflow_key`, edited in place. There is no publishing step and
no draft state: a saved workflow is what the agent sees, and `agent_enabled`
alone decides whether it may be selected — the same switch tools use.
"""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug
from app.dal.repository.validation import validate_steps


class WorkflowRepository:
    _validate_steps = staticmethod(validate_steps)

    def list_workflows(self) -> List[dict]:
        rows = self._all("SELECT * FROM summary_workflows ORDER BY name")
        return self._with_steps(rows)

    def get_workflow(self, workflow_id: str) -> dict:
        row = self._one(
            "SELECT * FROM summary_workflows WHERE id=%s", (workflow_id,)
        )
        row["steps"] = self._steps(workflow_id)
        return row

    def create_workflow(self, data: dict) -> dict:
        workflow_key = data.get("workflow_key") or slug(data["name"])
        if self._key_taken("summary_workflows", "workflow_key", workflow_key):
            raise ValueError(
                "כבר קיים תהליך במפתח %s. יש לערוך אותו או לבחור שם אחר."
                % workflow_key
            )
        row_id = new_id()
        validate_steps(data.get("steps", []))
        self._validate_agent(data.get("agent_id"))
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_WORKFLOW, _workflow_values(row_id, workflow_key, data)
            )
            _insert_steps(connection, row_id, data.get("steps", []))
            connection.commit()
        return self.get_workflow(row_id)

    def update_workflow(self, workflow_id: str, data: dict) -> dict:
        """Edit a workflow in place.

        `workflow_key` is the identity the agent routes by and is never
        rewritten from the payload. Steps are replaced wholesale — they are
        positional and the canvas sends the whole array, so reconciling them
        row by row would only invent a diff neither side asked for.

        `validate_steps` is the whole gate. It runs here and on create, so a
        workflow that reached the table is structurally sound whether or not
        the agent is allowed to select it.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        self.get_workflow(workflow_id)
        steps = data.get("steps", [])
        validate_steps(steps)
        self._validate_agent(data.get("agent_id"))
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_WORKFLOW, _workflow_update_values(workflow_id, data)
            )
            connection.execute(
                "DELETE FROM workflow_steps WHERE workflow_id=%s",
                (workflow_id,),
            )
            _insert_steps(connection, workflow_id, steps)
            connection.commit()
        return self.get_workflow(workflow_id)

    def delete_workflow(self, workflow_id: str) -> dict:
        """Remove a workflow.

        `workflow_steps` cascades from `summary_workflows`, so the steps go
        with it. Evidence rows reference `workflow_id` without a foreign key
        and are deliberately left alone — they are the audit trail of runs that
        really happened, and a past summary stays traceable after the workflow
        that produced it is retired.
        """
        workflow = self._one(
            "SELECT workflow_key, name FROM summary_workflows WHERE id=%s",
            (workflow_id,),
        )
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM summary_workflows WHERE id=%s", (workflow_id,)
            )
            connection.commit()
        return {"deleted": workflow["workflow_key"], "name": workflow["name"]}

    def enabled_workflows(self, roles: List[str]) -> List[dict]:
        """The workflows the agent may select, by role."""
        rows = self._all("""
            SELECT * FROM summary_workflows
            WHERE agent_enabled IS TRUE AND role = ANY(%s)
            ORDER BY name
        """, (roles,))
        return self._with_steps(rows)

    def enabled_workflows_by_keys(
        self, keys: List[str], roles: List[str]
    ) -> List[dict]:
        """The workflows a specialist owns, in the order it lists them."""
        if not keys:
            return []
        rows = self._all("""
            SELECT * FROM summary_workflows
            WHERE agent_enabled IS TRUE AND workflow_key = ANY(%s)
              AND role = ANY(%s)
        """, (keys, roles))
        by_key = {row["workflow_key"]: row for row in self._with_steps(rows)}
        return [by_key[key] for key in keys if key in by_key]

    def _validate_agent(self, agent_id) -> None:
        """Refuse an assignment to a missing row or to non-agent content."""
        if not agent_id:
            return
        if not self._all("""
            SELECT id FROM agent_content
            WHERE id=%s AND kind='agent' LIMIT 1
        """, (agent_id,)):
            raise ValueError("הסוכן שנבחר אינו קיים")

    def _with_steps(self, rows: List[dict]) -> List[dict]:
        for row in rows:
            row["steps"] = self._steps(row["id"])
        return rows

    def _steps(self, workflow_id: str) -> List[dict]:
        return self._all("""
            SELECT
                id, workflow_id, position, step_key AS key, name,
                package_version_id, depends_on, input_source, input_field,
                input_value, summary_prompt
            FROM workflow_steps
            WHERE workflow_id=%s ORDER BY position
        """, (workflow_id,))


def _workflow_fields(data):
    """Every editable column, in the order both statements below use."""
    return (
        data["name"], data.get("description", ""), data.get("role", "detail"),
        data.get("agent_enabled", True), data.get("agent_id") or None,
        data.get("system_prompt", ""),
        Jsonb(data.get("output_schema", {})), Jsonb(data.get("examples", [])),
    )


def _workflow_values(row_id, workflow_key, data):
    return (row_id, workflow_key) + _workflow_fields(data)


def _workflow_update_values(workflow_id, data):
    return _workflow_fields(data) + (workflow_id,)


def _insert_steps(connection, workflow_id: str, steps: List[dict]) -> None:
    for position, step in enumerate(steps):
        connection.execute(_INSERT_STEP, _step_values(
            workflow_id, position, step
        ))


def _step_values(workflow_id, position, step):
    return (
        new_id(), workflow_id, position, step["key"], step["name"],
        step["package_version_id"], Jsonb(step.get("depends_on", [])),
        step.get("input_source", "workflow.id"),
        step.get("input_field", ""), step.get("input_value", ""),
        step.get("summary_prompt", ""),
    )


_INSERT_WORKFLOW = """
    INSERT INTO summary_workflows (
        id, workflow_key, name, description, role,
        agent_enabled, agent_id, system_prompt, output_schema, examples
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_UPDATE_WORKFLOW = """
    UPDATE summary_workflows SET
        name=%s, description=%s, role=%s, agent_enabled=%s,
        agent_id=%s, system_prompt=%s, output_schema=%s, examples=%s
    WHERE id=%s
"""

_INSERT_STEP = """
    INSERT INTO workflow_steps (
        id, workflow_id, position, step_key, name, package_version_id,
        depends_on, input_source, input_field, input_value, summary_prompt
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

