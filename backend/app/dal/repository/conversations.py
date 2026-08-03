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

    def conversation_history(
        self, conversation_id: str, limit: int = 8
    ) -> List[dict]:
        """The conversation's finished turns, oldest first.

        Derived from `summary_runs` rather than stored separately: a run
        already holds the user's `question` and the assistant's `result`, so
        a parallel messages table would be a second source of truth that
        drifts whenever a run fails, retries, or is recovered at startup.

        Only finished runs are returned — a queued or failed run has no
        answer, and offering it as conversational context would invite the
        model to treat a question that was never answered as if it had been.
        The newest `limit` turns are selected, then reversed, so a long thread
        keeps its most recent context rather than its oldest.
        """
        rows = self._all("""
            SELECT id, question, result, status, created_at
            FROM summary_runs
            WHERE conversation_id=%s AND status IN ('completed','partial')
            ORDER BY created_at DESC LIMIT %s
        """, (conversation_id, max(1, limit)))
        return [_turn(row) for row in reversed(rows)]

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
