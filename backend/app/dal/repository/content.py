"""Versioned Skills and prompt persistence."""

from typing import List

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id, slug


class ContentRepository:
    def list_agent_content(self) -> List[dict]:
        return self._all("""
            SELECT DISTINCT ON (content_key) *
            FROM agent_content
            ORDER BY content_key, version DESC
        """)

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

    def create_agent_content(self, data: dict) -> dict:
        content_key = data.get("content_key") or slug(data["name"])
        version = self._next_version(
            "agent_content", "content_key", content_key
        )
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_CONTENT,
                _content_values(row_id, content_key, version, data),
            )
            connection.commit()
        return self._one("SELECT * FROM agent_content WHERE id=%s", (row_id,))

    def publish_agent_content(self, version_id: str) -> dict:
        item = self._one(
            "SELECT * FROM agent_content WHERE id=%s", (version_id,)
        )
        with connect(self._store) as connection:
            connection.execute(_ARCHIVE_CONTENT, (item["content_key"],))
            connection.execute(_PUBLISH_CONTENT, (version_id,))
            connection.commit()
        return self._one(
            "SELECT * FROM agent_content WHERE id=%s", (version_id,)
        )

    def published_content(self, key: str, fallback: str) -> str:
        rows = self._all("""
            SELECT content FROM agent_content
            WHERE content_key=%s AND status='published'
            ORDER BY version DESC LIMIT 1
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


def _content_values(row_id, content_key, version, data):
    return (
        row_id, content_key, version, data["kind"], data["name"],
        data.get("description", ""), data["content"],
        data.get("user_selectable", False),
    )


_INSERT_CONTENT = """
    INSERT INTO agent_content (
        id, content_key, version, kind, name, description,
        content, user_selectable, status
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')
"""

_ARCHIVE_CONTENT = """
    UPDATE agent_content SET status='archived'
    WHERE content_key=%s AND status='published'
"""

_PUBLISH_CONTENT = """
    UPDATE agent_content SET status='published', published_at=NOW()
    WHERE id=%s
"""
