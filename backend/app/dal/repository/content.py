"""Versioned Skills and prompt persistence."""

from typing import List

from psycopg.types.json import Jsonb

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

    def published_specialists(self) -> List[dict]:
        return self._all("""
            SELECT id, content_key, version, name, description, content, config
            FROM agent_content
            WHERE kind='agent' AND status='published'
            ORDER BY name
        """)

    def published_skill_options(self, keys: List[str]) -> List[dict]:
        return self._published_skills(keys, include_content=False)

    def published_skills(self, keys: List[str]) -> List[dict]:
        return self._published_skills(keys, include_content=True)

    def _published_skills(
        self, keys: List[str], include_content: bool
    ) -> List[dict]:
        if not keys:
            return []
        columns = (
            "id, content_key, version, name, description, content"
            if include_content
            else "id, content_key, version, name, description"
        )
        rows = self._all("""
            SELECT %s
            FROM agent_content
            WHERE kind='skill' AND status='published'
              AND content_key = ANY(%%s)
        """ % columns, (keys,))
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
        if item["kind"] == "agent":
            self._validate_specialist(item)
        with connect(self._store) as connection:
            connection.execute(_ARCHIVE_CONTENT, (item["content_key"],))
            connection.execute(_PUBLISH_CONTENT, (version_id,))
            connection.commit()
        return self._one(
            "SELECT * FROM agent_content WHERE id=%s", (version_id,)
        )

    def _validate_specialist(self, item: dict) -> None:
        config = item.get("config") if isinstance(item.get("config"), dict) else {}
        workflows = _keys(config.get("workflow_keys"))
        skills = _keys(config.get("skill_keys"))
        if not workflows:
            raise ValueError("נדרש לפחות Workflow מפורסם אחד לסוכן מומחה")
        available = {
            row["workflow_key"] for row in self._all("""
                SELECT workflow_key FROM summary_workflows
                WHERE status='published' AND workflow_key = ANY(%s)
            """, (workflows,))
        }
        missing = [key for key in workflows if key not in available]
        if missing:
            raise ValueError(
                "אי אפשר לפרסם סוכן עם Workflows שאינם מפורסמים: "
                + ", ".join(missing)
            )
        available_skills = {
            row["content_key"] for row in self._all("""
                SELECT content_key FROM agent_content
                WHERE kind='skill' AND status='published'
                  AND content_key = ANY(%s)
            """, (skills,))
        } if skills else set()
        missing_skills = [key for key in skills if key not in available_skills]
        if missing_skills:
            raise ValueError(
                "אי אפשר לפרסם סוכן עם Skills שאינם מפורסמים: "
                + ", ".join(missing_skills)
            )
        overlaps = []
        for other in self._all("""
            SELECT content_key, name, config FROM agent_content
            WHERE kind='agent' AND status='published' AND content_key<>%s
        """, (item["content_key"],)):
            shared = set(workflows).intersection(
                _keys((other.get("config") or {}).get("workflow_keys"))
            )
            if shared:
                overlaps.append("%s: %s" % (
                    other["name"], ", ".join(sorted(shared))
                ))
        if overlaps:
            raise ValueError(
                "כל Workflow יכול להשתייך לסוכן מפורסם אחד בלבד. "
                + "; ".join(overlaps)
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
        Jsonb(data.get("config", {})), data.get("user_selectable", False),
    )


def _keys(value) -> List[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(
        item.strip() for item in value
        if isinstance(item, str) and item.strip()
    ))


_INSERT_CONTENT = """
    INSERT INTO agent_content (
        id, content_key, version, kind, name, description,
        content, config, user_selectable, status
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft')
"""

_ARCHIVE_CONTENT = """
    UPDATE agent_content SET status='archived'
    WHERE content_key=%s AND status='published'
"""

_PUBLISH_CONTENT = """
    UPDATE agent_content SET status='published', published_at=NOW()
    WHERE id=%s
"""
