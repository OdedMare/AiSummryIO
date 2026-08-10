"""Skills and prompt persistence.

One row per `content_key`: an FDE edit updates the Skill or prompt in place
rather than appending a version, so a published Skill stays published across
an edit instead of being hidden behind a newer draft.
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
            WHERE kind='skill' AND status='published'
              AND user_selectable IS TRUE
            ORDER BY name
        """)

    def published_summary_skills(self, keys: List[str]) -> List[dict]:
        if not keys:
            return []
        rows = self._all("""
            SELECT content_key, name, description, content
            FROM agent_content
            WHERE kind='skill' AND status='published'
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
        """Edit a Skill or prompt in place, keeping its publication state.

        `content_key` is the identity `published_content` and the Skill
        catalog look up by, so it is never rewritten from the payload. Unlike
        a workflow there is nothing to validate: the content is free text and
        a published Skill has no mapping that an edit could break.
        """
        # `_one` raises NotFoundError (404) when the id is unknown.
        self.get_agent_content(content_id)
        with connect(self._store) as connection:
            connection.execute(
                _UPDATE_CONTENT, _content_update_values(content_id, data)
            )
            connection.commit()
        return self.get_agent_content(content_id)

    def publish_agent_content(self, content_id: str) -> dict:
        self.get_agent_content(content_id)
        with connect(self._store) as connection:
            connection.execute(_PUBLISH_CONTENT, (content_id,))
            connection.commit()
        return self.get_agent_content(content_id)

    def published_content(self, key: str, fallback: str) -> str:
        rows = self._all("""
            SELECT content FROM agent_content
            WHERE content_key=%s AND status='published'
        """, (key,))
        return rows[0]["content"] if rows else fallback

    def _seed_agent_content(self, items: List[dict]) -> None:
        for item in items:
            if not self._content_exists(item["content_key"]):
                created = self.create_agent_content(item)
                self.publish_agent_content(created["id"])

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
    )


def _content_values(row_id, content_key, data):
    return (row_id, content_key) + _content_fields(data)


def _content_update_values(content_id, data):
    return _content_fields(data) + (content_id,)


_INSERT_CONTENT = """
    INSERT INTO agent_content (
        id, content_key, kind, name, description,
        content, user_selectable, status
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,'draft')
"""

# `status` is deliberately absent, as on workflows: an edit changes the
# content, never whether it is published.
_UPDATE_CONTENT = """
    UPDATE agent_content SET
        kind=%s, name=%s, description=%s, content=%s, user_selectable=%s
    WHERE id=%s
"""

_PUBLISH_CONTENT = """
    UPDATE agent_content SET status='published', published_at=NOW()
    WHERE id=%s
"""
