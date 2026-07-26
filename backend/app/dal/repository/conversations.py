"""Conversation persistence and retention."""

from datetime import datetime, timedelta, timezone
from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class ConversationRepository:
    def create_conversation(
        self, session_id: str, root_id: str, boundaries=None
    ) -> dict:
        row_id = new_id()
        retention = self._store.get().conversation_retention_days
        expires = datetime.now(timezone.utc) + timedelta(days=retention)
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_CONVERSATION,
                (
                    row_id, session_id, root_id,
                    Jsonb(boundaries) if boundaries else None, expires,
                ),
            )
            connection.commit()
        return self.get_conversation(row_id, session_id)

    def get_conversation(
        self, conversation_id: str, session_id=None
    ) -> dict:
        condition, params = _conversation_filter(conversation_id, session_id)
        row = self._one(
            "SELECT * FROM conversations WHERE " + condition, params
        )
        row["runs"] = self._all("""
            SELECT * FROM summary_runs
            WHERE conversation_id=%s ORDER BY created_at
        """, (conversation_id,))
        return row

    def list_conversations(self, session_id: str) -> List[dict]:
        return self._all("""
            SELECT c.*, (
                SELECT status FROM summary_runs r
                WHERE r.conversation_id=c.id
                ORDER BY r.created_at DESC LIMIT 1
            ) AS last_status
            FROM conversations c
            WHERE session_id=%s AND expires_at > NOW()
            ORDER BY updated_at DESC LIMIT 30
        """, (session_id,))


def _conversation_filter(conversation_id: str, session_id):
    if session_id:
        return "id=%s AND session_id=%s", (conversation_id, session_id)
    return "id=%s", (conversation_id,)


_INSERT_CONVERSATION = """
    INSERT INTO conversations
        (id, session_id, root_id, boundaries, expires_at)
    VALUES (%s,%s,%s,%s,%s)
"""
