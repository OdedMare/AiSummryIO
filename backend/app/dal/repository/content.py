"""Skills, prompt, and specialist persistence.

One row per `content_key`, edited in place. There is no publishing step and no
draft state: a saved Skill, prompt, or specialist is what the agent sees, and
`agent_enabled` alone decides whether it may be used.

A specialist (`kind='agent'`) owns a set of workflows, so enabling one is the
moment its configuration has to hold together — see `_validate_specialist`.
"""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug


class ContentRepository:
    def prompt_revision(self) -> str:
        """Stable fingerprint of the live model instructions used by runs."""
        row = self._one("""
            SELECT md5(COALESCE(string_agg(item.value, E'\n'
                       ORDER BY item.key), '')) AS revision
            FROM (
                SELECT 'content:' || content_key AS key, content AS value
                FROM agent_content WHERE agent_enabled IS TRUE
                UNION ALL
                SELECT 'workflow:' || workflow_key, system_prompt
                FROM summary_workflows WHERE agent_enabled IS TRUE
                UNION ALL
                SELECT 'step:' || workflow_id || ':' || step_key,
                       summary_prompt
                FROM workflow_steps
            ) item
        """)
        return str(row.get("revision") or "")[:12]

    def list_agent_content(self, project_id=None) -> List[dict]:
        if project_id:
            rows = self._all("""
                SELECT * FROM agent_content
                WHERE project_id=%s ORDER BY name
            """, (project_id,))
        else:
            rows = self._all("SELECT * FROM agent_content ORDER BY name")
        return self._with_workflow_keys(
            rows
        )

    def list_summary_skills(self, project_id=None) -> List[dict]:
        project_filter = " AND project_id=%s" if project_id else ""
        params = (project_id,) if project_id else ()
        return self._all("""
            SELECT content_key, name, description
            FROM agent_content
            WHERE kind='skill' AND agent_enabled IS TRUE
              AND user_selectable IS TRUE
        """ + project_filter + """
            ORDER BY name
        """, params)

    def enabled_summary_skills(self, keys: List[str]) -> List[dict]:
        if not keys:
            return []
        rows = self._all("""
            SELECT content_key, name, description, content
            FROM agent_content
            WHERE kind='skill' AND agent_enabled IS TRUE
              AND user_selectable IS TRUE AND content_key = ANY(%s)
        """, (keys,))
        by_key = {row["content_key"]: row for row in rows}
        return [by_key[key] for key in keys if key in by_key]

    def enabled_specialists(self, keys=None) -> List[dict]:
        """The specialists the leader may delegate to."""
        params = ()
        selected = _keys(keys)
        where = ""
        if selected:
            where = " AND content_key = ANY(%s)"
            params = (selected,)
        rows = self._with_workflow_keys(self._all("""
            SELECT id, project_id, content_key, kind, name, description,
                   content, config
            FROM agent_content
            WHERE kind='agent' AND agent_enabled IS TRUE""" + where + """
            ORDER BY name
        """, params))
        if not selected:
            return rows
        by_key = {row["content_key"]: row for row in rows}
        return [by_key[key] for key in selected if key in by_key]

    def enabled_skill_options(self, keys: List[str]) -> List[dict]:
        return self._enabled_skills(keys, include_content=False)

    def enabled_skills(self, keys: List[str]) -> List[dict]:
        return self._enabled_skills(keys, include_content=True)

    def _enabled_skills(
        self, keys: List[str], include_content: bool
    ) -> List[dict]:
        if not keys:
            return []
        columns = (
            "id, content_key, name, description, content"
            if include_content
            else "id, content_key, name, description"
        )
        rows = self._all("""
            SELECT %s
            FROM agent_content
            WHERE kind='skill' AND agent_enabled IS TRUE
              AND content_key = ANY(%%s)
        """ % columns, (keys,))
        by_key = {row["content_key"]: row for row in rows}
        return [by_key[key] for key in keys if key in by_key]

    def get_agent_content(self, content_id: str) -> dict:
        return self._with_workflow_keys([self._one(
            "SELECT * FROM agent_content WHERE id=%s", (content_id,)
        )])[0]

    def create_agent_content(self, data: dict, project_id=None) -> dict:
        content_key = data.get("content_key") or slug(data["name"])
        if self._key_taken("agent_content", "content_key", content_key):
            raise ValueError(
                "כבר קיים פריט במפתח %s. יש לערוך אותו או לבחור שם אחר."
                % content_key
            )
        row_id = new_id()
        item = dict(
            data, id=row_id, content_key=content_key, project_id=project_id
        )
        self._validate_enabled(item)
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_CONTENT,
                _content_values(row_id, content_key, data, project_id),
            )
            _set_agent_workflows(connection, row_id, item)
            connection.commit()
        return self.get_agent_content(row_id)

    def update_agent_content(
        self, content_id: str, data: dict, project_id=None
    ) -> dict:
        """Edit a Skill, prompt, or specialist in place.

        `content_key` is the identity `enabled_content`, the Skill catalog, and
        a specialist's own config look up by, so it is never rewritten from the
        payload.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        current = self._owned_content(content_id, project_id)
        item = dict(
            data, id=content_id, content_key=current["content_key"],
            project_id=current.get("project_id"),
        )
        self._validate_enabled(item)
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_CONTENT, _content_update_values(content_id, data)
            )
            _set_agent_workflows(
                connection, content_id, item,
                was_agent=current.get("kind") == "agent",
            )
            connection.commit()
        return self.get_agent_content(content_id)

    def delete_agent_content(self, content_id: str, project_id=None) -> dict:
        """Remove a Skill, prompt, or specialist.

        Nothing pins one by row id, so unlike a tool wired into a workflow
        there is no reference that has to block the delete: a Skill is
        selected by `content_key` at request time, and `enabled_content`
        already falls back to the file-based prompt under `bl/prompts/` when
        the key is missing. Deleting the `workflow-planner` prompt therefore
        returns it to that default rather than breaking planning.

        A built-in Skill or prompt comes back at the next startup, because
        seeding keys on the row's absence — the same as the example tool and
        workflow. Deleting one is a way to reset it, not to remove it.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        item = self._owned_content(content_id, project_id)
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM agent_content WHERE id=%s", (content_id,)
            )
            connection.commit()
        return {"deleted": item["content_key"], "name": item["name"]}

    def _owned_content(self, content_id: str, project_id=None) -> dict:
        if project_id:
            return self._with_workflow_keys([self._one("""
                SELECT * FROM agent_content WHERE id=%s AND project_id=%s
            """, (content_id, project_id))])[0]
        return self.get_agent_content(content_id)

    def _validate_enabled(self, data: dict) -> None:
        """Gate a specialist on the way in, when it is enabled.

        Publishing used to be where this ran. With publishing gone, enabling
        is the moment the configuration starts being used, so it is the moment
        it has to hold together. A disabled specialist is skipped for the same
        reason a draft was: it is not routing anything yet, and half-built
        work must stay savable.
        """
        if data.get("kind") != "agent":
            return
        self._validate_workflow_ownership(data)
        if not data.get("agent_enabled", True):
            return
        self._validate_specialist(data)

    def _validate_workflow_ownership(self, item: dict) -> None:
        """A workflow has one owner, regardless of either enabled switch."""
        workflows = _keys((item.get("config") or {}).get("workflow_keys"))
        if not workflows:
            return
        rows = self._all("""
            SELECT workflow.workflow_key, workflow.agent_id,
                   owner.name AS agent_name
            FROM summary_workflows AS workflow
            LEFT JOIN agent_content AS owner ON owner.id=workflow.agent_id
            WHERE workflow.workflow_key = ANY(%s)
              AND workflow.project_id IS NOT DISTINCT FROM %s
        """, (workflows, item.get("project_id")))
        by_key = {row["workflow_key"]: row for row in rows}
        missing = [key for key in workflows if key not in by_key]
        if missing:
            raise ValueError(
                "Workflows לא קיימים: " + ", ".join(missing)
            )
        conflicts = [
            "%s: %s" % (row["agent_name"], key)
            for key, row in by_key.items()
            if row.get("agent_id") and row["agent_id"] != item.get("id")
        ]
        if conflicts:
            raise ValueError(
                "כל Workflow יכול להשתייך לסוכן אחד בלבד. "
                + "; ".join(conflicts)
            )

    def _validate_specialist(self, item: dict) -> None:
        config = item.get("config") if isinstance(item.get("config"), dict) else {}
        workflows = _keys(config.get("workflow_keys"))
        skills = _keys(config.get("skill_keys"))
        if not workflows:
            raise ValueError("נדרש לפחות Workflow פעיל אחד לסוכן מומחה")
        available = {
            row["workflow_key"] for row in self._all("""
                SELECT workflow_key FROM summary_workflows
                WHERE agent_enabled IS TRUE AND workflow_key = ANY(%s)
                  AND project_id IS NOT DISTINCT FROM %s
            """, (workflows, item.get("project_id")))
        }
        missing = [key for key in workflows if key not in available]
        if missing:
            raise ValueError(
                "אי אפשר להפעיל סוכן עם Workflows שאינם פעילים: "
                + ", ".join(missing)
            )
        available_skills = {
            row["content_key"] for row in self._all("""
                SELECT content_key FROM agent_content
                WHERE kind='skill' AND agent_enabled IS TRUE
                  AND content_key = ANY(%s)
                  AND project_id IS NOT DISTINCT FROM %s
            """, (skills, item.get("project_id")))
        } if skills else set()
        missing_skills = [key for key in skills if key not in available_skills]
        if missing_skills:
            raise ValueError(
                "אי אפשר להפעיל סוכן עם Skills שאינם פעילים: "
                + ", ".join(missing_skills)
            )

    def _with_workflow_keys(self, rows: List[dict]) -> List[dict]:
        """Expose the old API shape from the relational source of truth."""
        agent_ids = [row["id"] for row in rows if row.get("kind") == "agent"]
        if not agent_ids:
            return rows
        owned = self._all("""
            SELECT agent_id, workflow_key FROM summary_workflows
            WHERE agent_id = ANY(%s) ORDER BY name
        """, (agent_ids,))
        by_agent = {agent_id: [] for agent_id in agent_ids}
        for workflow in owned:
            by_agent[workflow["agent_id"]].append(workflow["workflow_key"])
        for row in rows:
            if row.get("kind") != "agent":
                continue
            row["config"] = dict(row.get("config") or {})
            row["config"]["workflow_keys"] = by_agent[row["id"]]
        return rows

    def enabled_content(self, key: str, fallback: str) -> str:
        """The prompt text for `key`, or the caller's built-in default.

        A disabled or deleted prompt therefore returns the version under
        `bl/prompts/` rather than failing — turning one off is a way back to
        the shipped wording.
        """
        rows = self._all("""
            SELECT content FROM agent_content
            WHERE content_key=%s AND agent_enabled IS TRUE
        """, (key,))
        return rows[0]["content"] if rows else fallback

    def _seed_agent_content(self, items: List[dict]) -> None:
        for item in items:
            if not self._content_exists(item["content_key"]):
                self.create_agent_content(item)

    def _content_exists(self, content_key: str) -> bool:
        return bool(self._all(
            "SELECT id FROM agent_content WHERE content_key=%s LIMIT 1",
            (content_key,),
        ))


def _content_fields(data):
    """Every editable column, in the order both statements below use."""
    config = dict(data.get("config") or {})
    if data.get("kind") == "agent":
        config.pop("workflow_keys", None)
    return (
        data["kind"], data["name"], data.get("description", ""),
        data["content"], Jsonb(config),
        data.get("user_selectable", False), data.get("agent_enabled", True),
    )


def _content_values(row_id, content_key, data, project_id=None):
    return (row_id, content_key, project_id) + _content_fields(data)


def _content_update_values(content_id, data):
    return _content_fields(data) + (content_id,)


def _keys(value) -> List[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(
        item.strip() for item in value
        if isinstance(item, str) and item.strip()
    ))


def _set_agent_workflows(
    connection, content_id: str, item: dict, was_agent: bool = False
) -> None:
    if item.get("kind") != "agent" and not was_agent:
        return
    connection.execute(
        "UPDATE summary_workflows SET agent_id=NULL WHERE agent_id=%s",
        (content_id,),
    )
    if item.get("kind") != "agent":
        return
    keys = _keys((item.get("config") or {}).get("workflow_keys"))
    if keys:
        connection.execute("""
            UPDATE summary_workflows SET agent_id=%s
            WHERE workflow_key = ANY(%s)
              AND project_id IS NOT DISTINCT FROM %s
        """, (content_id, keys, item.get("project_id")))


_INSERT_CONTENT = """
    INSERT INTO agent_content (
        id, content_key, project_id, kind, name, description,
        content, config, user_selectable, agent_enabled
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_UPDATE_CONTENT = """
    UPDATE agent_content SET
        kind=%s, name=%s, description=%s, content=%s, config=%s,
        user_selectable=%s, agent_enabled=%s
    WHERE id=%s
"""
