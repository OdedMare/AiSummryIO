"""Skills and prompt persistence.

One row per `content_key`, edited in place. There is no publishing step and no
draft state: a saved Skill or prompt is what the agent sees, and
`agent_enabled` alone decides whether it may be used.
"""

from typing import List

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug


class ContentRepository:
    def list_agent_content(self) -> List[dict]:
        return self._all("SELECT * FROM agent_content ORDER BY name")

    def list_summary_skills(self) -> List[dict]:
        return self._all("""
            SELECT content_key, name, description
            FROM agent_content
            WHERE kind='skill' AND agent_enabled IS TRUE
              AND user_selectable IS TRUE
            ORDER BY name
        """)

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

    def get_agent_content(self, content_id: str) -> dict:
        return self._one(
            "SELECT * FROM agent_content WHERE id=%s", (content_id,)
        )

    def create_agent_content(self, data: dict) -> dict:
        content_key = data.get("content_key") or slug(data["name"])
        if self._key_taken("agent_content", "content_key", content_key):
            raise ValueError(
                "כבר קיים פריט במפתח %s. יש לערוך אותו או לבחור שם אחר."
                % content_key
            )
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_CONTENT, _content_values(row_id, content_key, data)
            )
            connection.commit()
        return self.get_agent_content(row_id)

    def update_agent_content(self, content_id: str, data: dict) -> dict:
        """Edit a Skill or prompt in place.

        `content_key` is the identity `enabled_content` and the Skill catalog
        look up by, so it is never rewritten from the payload. Unlike a
        workflow there is nothing to validate: the content is free text with
        no mapping an edit could break.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        self.get_agent_content(content_id)
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_CONTENT, _content_update_values(content_id, data)
            )
            connection.commit()
        return self.get_agent_content(content_id)

    def delete_agent_content(self, content_id: str) -> dict:
        """Remove a Skill or prompt.

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
        item = self._one(
            "SELECT content_key, name FROM agent_content WHERE id=%s",
            (content_id,),
        )
        with connect(self._store) as connection:
            connection.execute(
                "DELETE FROM agent_content WHERE id=%s", (content_id,)
            )
            connection.commit()
        return {"deleted": item["content_key"], "name": item["name"]}

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
    return (
        data["kind"], data["name"], data.get("description", ""),
        data["content"], data.get("user_selectable", False),
        data.get("agent_enabled", True),
    )


def _content_values(row_id, content_key, data):
    return (row_id, content_key) + _content_fields(data)


def _content_update_values(content_id, data):
    return _content_fields(data) + (content_id,)


_INSERT_CONTENT = """
    INSERT INTO agent_content (
        id, content_key, kind, name, description,
        content, user_selectable, agent_enabled
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
"""

_UPDATE_CONTENT = """
    UPDATE agent_content SET
        kind=%s, name=%s, description=%s, content=%s,
        user_selectable=%s, agent_enabled=%s
    WHERE id=%s
"""
