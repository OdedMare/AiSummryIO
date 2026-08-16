"""Conversation persistence and retention."""

from datetime import datetime, timedelta, timezone
from typing import List

from psycopg.types.json import Jsonb

from app.common.errors import ConflictError, NotFoundError
from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class ConversationRepository:
    def create_conversation(
        self, session_id: str, root_id: str, boundaries=None, title: str = ""
    ) -> dict:
        row_id = new_id()
        idle_minutes = self._store.get().conversation_idle_minutes
        expires = datetime.now(timezone.utc) + timedelta(minutes=idle_minutes)
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_CONVERSATION,
                (
                    row_id, session_id, root_id,
                    Jsonb(boundaries) if boundaries else None, expires,
                    conversation_title(title),
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
        self.purge_expired_conversations()
        return self._all("""
            SELECT c.*, (
                SELECT status FROM summary_runs r
                WHERE r.conversation_id=c.id
                ORDER BY r.created_at DESC LIMIT 1
            ) AS last_status
            FROM conversations c
            WHERE session_id=%s AND expires_at > NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM evaluation_cases evaluation
                  WHERE evaluation.conversation_id=c.id
              )
            ORDER BY updated_at DESC LIMIT 30
        """, (session_id,))

    def purge_expired_conversations(self) -> int:
        """Remove idle conversations, except work that is still executing."""
        with connect(self._store) as connection:
            rows = connection.execute("""
                DELETE FROM conversations AS conversation
                WHERE expires_at <= NOW()
                  AND NOT EXISTS (
                      SELECT 1 FROM evaluation_cases evaluation
                      WHERE evaluation.conversation_id=conversation.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM summary_runs
                      WHERE conversation_id=conversation.id
                        AND status IN ('queued','running')
                  )
                RETURNING id
            """).fetchall()
            connection.commit()
        return len(rows)

    def delete_conversation(self, conversation_id: str, session_id: str) -> dict:
        """Delete one idle, owned conversation and all of its heavy evidence.

        The schema's two ON DELETE CASCADE links remove runs, evidence, and
        feedback in the same transaction. Active work is rejected so a worker
        cannot recreate progress after its parent conversation disappeared.
        """
        with connect(self._store) as connection:
            conversation = connection.execute("""
                SELECT id, title FROM conversations
                WHERE id=%s AND session_id=%s
            """, (conversation_id, session_id)).fetchone()
            if not conversation:
                raise NotFoundError("השיחה לא נמצאה")
            evaluation = connection.execute("""
                SELECT 1 FROM evaluation_cases
                WHERE conversation_id=%s
                LIMIT 1
            """, (conversation_id,)).fetchone()
            if evaluation:
                raise ConflictError(
                    "שיחה ששייכת ל-Evaluation נמחקת רק דרך מחיקת הסשן"
                )
            active = connection.execute("""
                SELECT 1 FROM summary_runs
                WHERE conversation_id=%s AND status IN ('queued','running')
                LIMIT 1
            """, (conversation_id,)).fetchone()
            if active:
                raise ConflictError("לא ניתן למחוק שיחה בזמן שהסיכום עדיין מופק")
            connection.execute(
                "DELETE FROM conversations WHERE id=%s", (conversation_id,)
            )
            connection.commit()
        return {"deleted": conversation_id, "title": conversation["title"]}


_TITLE_LIMIT = 80


def conversation_title(question: str) -> str:
    """The opening question, collapsed and bounded, as a thread title.

    Truncation is on a word boundary when one is close enough to the limit,
    so a title breaks between words rather than mid-word.
    """
    text = " ".join((question or "").split())
    if len(text) <= _TITLE_LIMIT:
        return text
    clipped = text[:_TITLE_LIMIT]
    spaced = clipped.rsplit(" ", 1)[0]
    return (spaced if len(spaced) > _TITLE_LIMIT // 2 else clipped) + "…"


def _turn(row: dict) -> dict:
    """One run projected as a question/answer pair.

    The answer is the headline and summary only. The rest of `result` is
    facts and sections already carried into routing as evidence, so
    including it here would spend the context budget twice on the same data.
    """
    result = row.get("result") or {}
    return {
        "run_id": row["id"],
        "question": row.get("question") or "",
        "answer": _answer(result),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _answer(result: dict) -> str:
    headline = (result.get("headline") or "").strip()
    summary = (result.get("summary") or "").strip()
    if headline and summary and not summary.startswith(headline):
        return headline + "\n" + summary
    return summary or headline


def _conversation_filter(conversation_id: str, session_id):
    if session_id:
        return "id=%s AND session_id=%s", (conversation_id, session_id)
    return "id=%s", (conversation_id,)


_INSERT_CONVERSATION = """
    INSERT INTO conversations
        (id, session_id, root_id, boundaries, expires_at, title)
    VALUES (%s,%s,%s,%s,%s,%s)
"""
