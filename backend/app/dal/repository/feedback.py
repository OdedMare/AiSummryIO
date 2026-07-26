"""Summary feedback and review-queue persistence."""

from typing import List

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class FeedbackRepository:
    def save_feedback(self, session_id: str, data: dict) -> dict:
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_FEEDBACK,
                (
                    row_id, data["run_id"], session_id, data["rating"],
                    data.get("comment", ""),
                ),
            )
            connection.commit()
        return {"id": row_id}

    def review_queue(self) -> List[dict]:
        return self._all("""
            SELECT f.*, r.kind, r.status AS run_status, r.error
            FROM summary_feedback f
            JOIN summary_runs r ON r.id=f.run_id
            WHERE f.rating < 0 OR COALESCE(f.comment, '') <> ''
            ORDER BY f.created_at DESC LIMIT 100
        """)


_INSERT_FEEDBACK = """
    INSERT INTO summary_feedback (
        id, run_id, session_id, rating, comment
    ) VALUES (%s,%s,%s,%s,%s)
"""
