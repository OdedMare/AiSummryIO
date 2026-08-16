"""Summary feedback, the review queue, and per-route rating aggregates."""

from typing import Dict, List

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
        """Runs an admin should look at: a poor rating or any left comment."""
        return self._all("""
            SELECT f.*, r.kind, r.status AS run_status, r.error
            FROM summary_feedback f
            JOIN summary_runs r ON r.id=f.run_id
            WHERE f.rating <= 2 OR COALESCE(f.comment, '') <> ''
            ORDER BY f.created_at DESC LIMIT 100
        """)

    def route_ratings(self) -> Dict[str, dict]:
        """Average star rating per route, keyed by `summary_evidence.workflow_id`.

        A route is a real workflow's row id, or `"tool:" + package_version_id`
        for a standalone tool (`routing.tool_workflow`) — either way it is
        exactly the key `_execute_workflow`/`_tool_step` pass to
        `save_evidence`, so the caller can look a route up by the same id it
        already has, with no join back to `summary_workflows` or
        `summary_packages` needed.

        `summary_feedback` rates a whole run's answer, not one route in
        isolation, so a run answered by several workflows counts its rating
        toward each of them. That is read here as "feedback on runs this
        route helped answer", not as a route-specific score — routing.py
        treats a low `rating_count` as too thin to trust for that reason.
        `DISTINCT` on evidence collapses a multi-step workflow's several
        evidence rows to one per run, so a 3-step workflow does not triple-
        count the same feedback.
        """
        rows = self._all("""
            WITH routes AS (
                SELECT DISTINCT run_id, workflow_id FROM summary_evidence
            )
            SELECT r.workflow_id AS route_id,
                   ROUND(AVG(f.rating)::numeric, 1) AS avg_rating,
                   COUNT(*) AS rating_count
            FROM summary_feedback f
            JOIN routes r ON r.run_id = f.run_id
            GROUP BY r.workflow_id
        """)
        return {row["route_id"]: row for row in rows}


_INSERT_FEEDBACK = """
    INSERT INTO summary_feedback (
        id, run_id, session_id, rating, comment
    ) VALUES (%s,%s,%s,%s,%s)
"""
