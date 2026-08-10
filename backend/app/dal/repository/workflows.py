"""Workflow and step persistence.

One row per `workflow_key`: an FDE edit updates the workflow in place rather
than appending a version. That is what keeps a published workflow published
across an edit — appending a draft used to hide the published row that was
still serving traffic, so the studio reported the workflow as unpublished
while it was in fact live.
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
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_WORKFLOW, _workflow_values(row_id, workflow_key, data)
            )
            _insert_steps(connection, row_id, data.get("steps", []))
            connection.commit()
        return self.get_workflow(row_id)

    def update_workflow(self, workflow_id: str, data: dict) -> dict:
        """Edit a workflow in place, keeping its publication state.

        A published workflow stays published through an edit, which is the
        point of dropping versions — but it is also live, so the edit has to
        clear the same bar publishing does. Saving steps that would fail
        `_validate_for_publish` onto a published workflow is refused rather
        than quietly demoted to a draft: silently unpublishing a route the
        agent is currently selecting is the failure this change exists to
        remove.

        `workflow_key` is the identity the agent routes by and is never
        rewritten from the payload. Steps are replaced wholesale — they are
        positional and the canvas sends the whole array, so reconciling them
        row by row would only invent a diff neither side asked for.
        """
        current = self.get_workflow(workflow_id)
        steps = data.get("steps", [])
        validate_steps(steps)
        if current["status"] == "published":
            self._validate_for_publish(dict(data, steps=steps))
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

    def publish_workflow(self, workflow_id: str) -> dict:
        workflow = self.get_workflow(workflow_id)
        self._validate_for_publish(workflow)
        with connect(self._store) as connection:
            connection.execute(_PUBLISH_WORKFLOW, (workflow_id,))
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

    def published_workflows(self, roles: List[str]) -> List[dict]:
        rows = self._all("""
            SELECT * FROM summary_workflows
            WHERE status='published' AND role = ANY(%s)
            ORDER BY name
        """, (roles,))
        return self._with_steps(rows)

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

    def _validate_for_publish(self, workflow: dict) -> None:
        if not workflow["steps"]:
            raise ValueError("אי אפשר לפרסם תהליך ללא שלבים")
        validate_steps(workflow["steps"])
        if workflow.get("examples"):
            return
        incomplete = self._packages_missing_examples(workflow)
        if not incomplete:
            return
        # Naming the packages is the whole point: the generic form of this
        # message left the FDE to open every tool in the workflow to find
        # which one was unfinished.
        raise ValueError(
            "נדרשת דוגמת תהליך, או דוגמאות קלט ופלט לכל חבילה, לפני פרסום. "
            "חסרות דוגמאות ב: %s" % "; ".join(incomplete)
        )

    def _packages_missing_examples(self, workflow: dict) -> List[str]:
        """Names of step packages lacking an input or output example."""
        missing = []
        for step in workflow["steps"]:
            item = self.get_package(step["package_version_id"])
            gaps = []
            if not item.get("example_input"):
                gaps.append("דוגמת קלט")
            if not item.get("example_output"):
                gaps.append("דוגמת פלט")
            if gaps:
                missing.append(
                    "%s (%s)" % (item.get("name", step["name"]), " ו".join(gaps))
                )
        return missing


def _workflow_fields(data):
    """Every editable column, in the order both statements below use."""
    return (
        data["name"], data.get("description", ""), data.get("role", "detail"),
        data.get("system_prompt", ""), Jsonb(data.get("output_schema", {})),
        Jsonb(data.get("examples", [])),
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
        status, system_prompt, output_schema, examples
    ) VALUES (%s,%s,%s,%s,%s,'draft',%s,%s,%s)
"""

# `status` is deliberately absent: an edit changes what the workflow does,
# never whether it is published.
_UPDATE_WORKFLOW = """
    UPDATE summary_workflows SET
        name=%s, description=%s, role=%s,
        system_prompt=%s, output_schema=%s, examples=%s
    WHERE id=%s
"""

_INSERT_STEP = """
    INSERT INTO workflow_steps (
        id, workflow_id, position, step_key, name, package_version_id,
        depends_on, input_source, input_field, input_value, summary_prompt
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_PUBLISH_WORKFLOW = """
    UPDATE summary_workflows SET status='published', published_at=NOW()
    WHERE id=%s
"""
