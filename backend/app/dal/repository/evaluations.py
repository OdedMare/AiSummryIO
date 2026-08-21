"""Persistent shared evaluation batches and their summary-run links."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from psycopg.types.json import Jsonb

from app.common.errors import ConflictError, NotFoundError
from app.dal.database.postgres import connect
from app.dal.repository.base import new_id
from app.dal.repository.conversations import conversation_title
from app.dal.repository.runs import _empty_progress


_ACTIVE = ("running", "pausing", "paused", "stopping")


class EvaluationRepository:
    def create_evaluation_batch(
        self, session_id: str, data: dict, root_ids: List[str]
    ) -> dict:
        batch_id = new_id()
        with connect(self._store) as connection:
            connection.execute("LOCK TABLE evaluation_batches IN SHARE ROW EXCLUSIVE MODE")
            active = connection.execute(
                "SELECT 1 FROM evaluation_batches WHERE status=ANY(%s) LIMIT 1",
                (list(_ACTIVE),),
            ).fetchone()
            if active:
                raise ConflictError("כבר קיימת ריצת Evaluation פעילה")
            connection.execute(
                """INSERT INTO evaluation_batches (
                       id, session_id, project_id, label, question,
                       skill_keys, agent_keys,
                       cooldown_seconds, status, next_start_at
                   ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'running',NOW())""",
                (
                    batch_id, session_id, data.get("project_id"),
                    data["label"], data["question"],
                    Jsonb(data.get("skill_keys") or []),
                    Jsonb(data.get("agent_keys") or []),
                    data.get("cooldown_seconds", 0),
                ),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO evaluation_cases (
                           id, batch_id, position, root_id
                       ) VALUES (%s,%s,%s,%s)""",
                    [
                        (new_id(), batch_id, position, root_id)
                        for position, root_id in enumerate(root_ids, start=1)
                    ],
                )
            connection.commit()
        return self.get_evaluation_batch(batch_id)

    def list_evaluation_batches(self, limit: int = 50) -> List[dict]:
        return self._all(_BATCH_SELECT + " ORDER BY batch.created_at DESC LIMIT %s", (limit,))

    def get_evaluation_batch(self, batch_id: str) -> dict:
        return self._one(_BATCH_SELECT + " WHERE batch.id=%s", (batch_id,))

    def active_evaluation_batch(self) -> Optional[dict]:
        rows = self._all(
            _BATCH_SELECT
            + " WHERE batch.status=ANY(%s) ORDER BY batch.created_at LIMIT 1",
            (list(_ACTIVE),),
        )
        return rows[0] if rows else None

    def list_evaluation_cases(
        self, batch_id: str, status: str = "", search: str = "",
        offset: int = 0, limit: int = 50,
    ) -> dict:
        self.get_evaluation_batch(batch_id)
        clauses = ["evaluation.batch_id=%s"]
        params = [batch_id]
        if status:
            clauses.append(_CASE_STATUS + "=%s")
            params.append(status)
        if search:
            clauses.append("evaluation.root_id ILIKE %s")
            params.append("%" + search + "%")
        where = " WHERE " + " AND ".join(clauses)
        count = self._all(
            "SELECT COUNT(*) AS total FROM evaluation_cases evaluation "
            "LEFT JOIN summary_runs run ON run.id=evaluation.run_id" + where,
            tuple(params),
        )[0]["total"]
        rows = self._all(
            _CASE_LIST_SELECT + where
            + " ORDER BY evaluation.position LIMIT %s OFFSET %s",
            tuple(params + [limit, offset]),
        )
        return {"items": rows, "total": count, "offset": offset, "limit": limit}

    def get_evaluation_case(self, batch_id: str, case_id: str) -> dict:
        return self._one(
            _CASE_DETAIL_SELECT
            + " WHERE evaluation.batch_id=%s AND evaluation.id=%s",
            (batch_id, case_id),
        )

    def evaluation_export_rows(self, batch_id: str) -> List[dict]:
        self.get_evaluation_batch(batch_id)
        return self._all(
            _CASE_DETAIL_SELECT
            + " WHERE evaluation.batch_id=%s ORDER BY evaluation.position",
            (batch_id,),
        )

    def update_evaluation_review(
        self, batch_id: str, case_id: str, rating, comment: str
    ) -> dict:
        with connect(self._store) as connection:
            updated = connection.execute(
                """UPDATE evaluation_cases
                   SET rating=%s, comment=%s, updated_at=NOW()
                   WHERE batch_id=%s AND id=%s RETURNING id""",
                (rating, comment, batch_id, case_id),
            ).fetchone()
            if not updated:
                raise NotFoundError("תוצאת ה-Evaluation לא נמצאה")
            connection.commit()
        return self.get_evaluation_case(batch_id, case_id)

    def change_evaluation_status(
        self, batch_id: str, target: str, allowed: tuple
    ) -> dict:
        with connect(self._store) as connection:
            updated = connection.execute(
                """UPDATE evaluation_batches
                   SET status=%s, updated_at=NOW(),
                       next_start_at=CASE WHEN %s='running' THEN NOW()
                                          ELSE next_start_at END
                   WHERE id=%s AND status=ANY(%s) RETURNING id""",
                (target, target, batch_id, list(allowed)),
            ).fetchone()
            if not updated:
                exists = connection.execute(
                    "SELECT status FROM evaluation_batches WHERE id=%s",
                    (batch_id,),
                ).fetchone()
                if not exists:
                    raise NotFoundError("ריצת ה-Evaluation לא נמצאה")
                raise ConflictError("הפעולה אינה זמינה במצב הנוכחי")
            connection.commit()
        return self.get_evaluation_batch(batch_id)

    def settle_evaluation(self, batch_id: str, target: str) -> None:
        finished = target in ("stopped", "completed")
        with connect(self._store) as connection:
            if target == "stopped":
                connection.execute(
                    """UPDATE evaluation_cases
                       SET status='stopped', updated_at=NOW()
                       WHERE batch_id=%s AND run_id IS NULL
                         AND status='pending'""",
                    (batch_id,),
                )
            connection.execute(
                """UPDATE evaluation_batches
                   SET status=%s, updated_at=NOW(),
                       finished_at=CASE WHEN %s THEN NOW() ELSE NULL END
                   WHERE id=%s""",
                (target, finished, batch_id),
            )
            connection.commit()

    def start_next_evaluation_case(self, batch_id: str) -> Optional[dict]:
        """Atomically bind one pending case to a normal conversation/run."""
        idle_minutes = self._store.get().conversation_idle_minutes
        now = datetime.now(timezone.utc)
        with connect(self._store) as connection:
            batch = connection.execute(
                """SELECT * FROM evaluation_batches
                   WHERE id=%s AND status='running'
                     AND next_start_at <= NOW() FOR UPDATE""",
                (batch_id,),
            ).fetchone()
            if not batch:
                return None
            case = connection.execute(
                """SELECT * FROM evaluation_cases
                   WHERE batch_id=%s AND run_id IS NULL AND status='pending'
                   ORDER BY position FOR UPDATE SKIP LOCKED LIMIT 1""",
                (batch_id,),
            ).fetchone()
            if not case:
                return None
            conversation_id, run_id = new_id(), new_id()
            expires = now + timedelta(minutes=idle_minutes)
            connection.execute(
                """INSERT INTO conversations
                       (id, session_id, root_id, boundaries, expires_at, title,
                        project_id)
                   VALUES (%s,%s,%s,NULL,%s,%s,%s)""",
                (
                    conversation_id, batch["session_id"], case["root_id"],
                    expires, conversation_title(batch["question"]),
                    batch.get("project_id"),
                ),
            )
            connection.execute(
                """INSERT INTO summary_runs (
                       id, conversation_id, kind, question, skill_keys,
                       agent_keys,
                       status, progress
                   ) VALUES (%s,%s,'full',%s,%s,%s,'queued',%s)""",
                (
                    run_id, conversation_id, batch["question"],
                    Jsonb(batch["skill_keys"]), Jsonb(batch["agent_keys"]),
                    Jsonb(_empty_progress()),
                ),
            )
            connection.execute(
                """UPDATE evaluation_cases
                   SET conversation_id=%s, run_id=%s, updated_at=NOW()
                   WHERE id=%s""",
                (conversation_id, run_id, case["id"]),
            )
            connection.execute(
                """UPDATE evaluation_batches
                   SET next_start_at=%s, updated_at=NOW() WHERE id=%s""",
                (
                    now + timedelta(seconds=batch["cooldown_seconds"]),
                    batch_id,
                ),
            )
            connection.commit()
        return {"case_id": case["id"], "run_id": run_id}

    def fail_evaluation_case(self, case_id: str, error: str) -> None:
        with connect(self._store) as connection:
            connection.execute(
                """UPDATE evaluation_cases SET status='failed', error=%s,
                       updated_at=NOW() WHERE id=%s""",
                (error[:5000], case_id),
            )
            connection.commit()

    def failed_evaluation_root_ids(self, batch_id: str) -> List[str]:
        rows = self._all(
            """SELECT evaluation.root_id
               FROM evaluation_cases evaluation
               LEFT JOIN summary_runs run ON run.id=evaluation.run_id
               WHERE evaluation.batch_id=%s AND """ + _CASE_STATUS + "='failed'"
               " ORDER BY evaluation.position",
            (batch_id,),
        )
        return [row["root_id"] for row in rows]

    def delete_evaluation_batch(self, batch_id: str) -> dict:
        with connect(self._store) as connection:
            batch = connection.execute(
                "SELECT id, label, status FROM evaluation_batches WHERE id=%s",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise NotFoundError("ריצת ה-Evaluation לא נמצאה")
            if batch["status"] in _ACTIVE:
                raise ConflictError("יש לעצור את הריצה לפני המחיקה")
            conversations = connection.execute(
                """SELECT conversation_id FROM evaluation_cases
                   WHERE batch_id=%s AND conversation_id IS NOT NULL""",
                (batch_id,),
            ).fetchall()
            conversation_ids = [row["conversation_id"] for row in conversations]
            connection.execute(
                "DELETE FROM evaluation_batches WHERE id=%s", (batch_id,)
            )
            if conversation_ids:
                connection.execute(
                    "DELETE FROM conversations WHERE id=ANY(%s)",
                    (conversation_ids,),
                )
            connection.commit()
        return {
            "deleted": batch_id,
            "label": batch["label"],
            "conversations": len(conversation_ids),
        }


_CASE_STATUS = "COALESCE(run.status, evaluation.status)"

_STATS_JOIN = """
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status='pending') AS pending,
        COUNT(*) FILTER (WHERE status='queued') AS queued,
        COUNT(*) FILTER (WHERE status='running') AS running,
        COUNT(*) FILTER (WHERE status='completed') AS completed,
        COUNT(*) FILTER (WHERE status='partial') AS partial,
        COUNT(*) FILTER (WHERE status='failed') AS failed,
        COUNT(*) FILTER (WHERE status='stopped') AS stopped,
        COUNT(rating) AS reviewed,
        ROUND(AVG(rating)::numeric, 2) AS average_rating,
        ROUND(AVG(quality_score)::numeric, 2) AS automatic_quality
    FROM (
        SELECT COALESCE(run.status, evaluation.status) AS status,
               evaluation.rating,
               CASE
                   WHEN jsonb_typeof(run.result->'quality'->'score')='number'
                   THEN (run.result->'quality'->>'score')::numeric
                   ELSE NULL
               END AS quality_score
        FROM evaluation_cases evaluation
        LEFT JOIN summary_runs run ON run.id=evaluation.run_id
        WHERE evaluation.batch_id=batch.id
    ) case_statuses
) stats ON TRUE
"""

_BATCH_SELECT = """
SELECT batch.*,
       COALESCE(stats.total, 0) AS total,
       COALESCE(stats.pending, 0) AS pending,
       COALESCE(stats.queued, 0) AS queued,
       COALESCE(stats.running, 0) AS running,
       COALESCE(stats.completed, 0) AS completed,
       COALESCE(stats.partial, 0) AS partial,
       COALESCE(stats.failed, 0) AS failed,
       COALESCE(stats.stopped, 0) AS stopped,
       COALESCE(stats.reviewed, 0) AS reviewed,
       stats.average_rating,
       stats.automatic_quality
FROM evaluation_batches batch
""" + _STATS_JOIN

_CASE_LIST_SELECT = """
SELECT evaluation.id, evaluation.batch_id, evaluation.position,
       evaluation.root_id, evaluation.rating, evaluation.comment,
       evaluation.error AS case_error, evaluation.run_id,
       """ + _CASE_STATUS + """ AS status,
       COALESCE(run.error, evaluation.error) AS error,
       run.result ->> 'headline' AS headline,
       run.result ->> 'summary' AS summary,
       EXTRACT(EPOCH FROM (run.finished_at - run.created_at)) AS duration_seconds
FROM evaluation_cases evaluation
LEFT JOIN summary_runs run ON run.id=evaluation.run_id
"""

_CASE_DETAIL_SELECT = """
SELECT evaluation.id, evaluation.batch_id, evaluation.position,
       evaluation.root_id, evaluation.rating, evaluation.comment,
       evaluation.error AS case_error, """ + _CASE_STATUS + """ AS status,
       run.id AS run_id, run.conversation_id, run.kind, run.question,
       run.skill_keys, run.agent_keys, run.status AS run_status, run.progress,
       run.result,
       run.result ->> 'headline' AS headline,
       run.result ->> 'summary' AS summary,
       COALESCE(run.error, evaluation.error) AS error,
       run.created_at AS run_created_at, run.finished_at,
       EXTRACT(EPOCH FROM (run.finished_at - run.created_at)) AS duration_seconds
FROM evaluation_cases evaluation
LEFT JOIN summary_runs run ON run.id=evaluation.run_id
"""
