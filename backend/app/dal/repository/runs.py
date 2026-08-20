"""Summary run progress and evidence persistence."""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class RunRepository:
    def create_run(
        self, conversation_id: str, question: str, kind: str, skill_keys=None,
        agent_keys=None,
    ) -> dict:
        row_id = new_id()
        idle_minutes = self._store.get().conversation_idle_minutes
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_RUN,
                (
                    row_id, conversation_id, kind, question,
                    Jsonb(skill_keys or []), Jsonb(agent_keys or []),
                    Jsonb(_empty_progress()),
                ),
            )
            connection.execute(
                """UPDATE conversations
                   SET updated_at=NOW(),
                       expires_at=NOW() + (%s * INTERVAL '1 minute')
                   WHERE id=%s""",
                (idle_minutes, conversation_id),
            )
            connection.commit()
        return self.get_run(row_id)

    def get_run(self, run_id: str) -> dict:
        return self._one(
            "SELECT * FROM summary_runs WHERE id=%s", (run_id,)
        )

    def queued_runs(self) -> List[dict]:
        with connect(self._store) as connection:
            connection.execute("""
                UPDATE summary_runs SET status='queued'
                WHERE status='running'
            """)
            connection.commit()
        return self._all("""
            SELECT * FROM summary_runs WHERE status='queued' ORDER BY created_at
        """)

    def update_run(self, run_id: str, **changes) -> dict:
        pairs, values = _run_changes(changes)
        if not pairs:
            return self.get_run(run_id)
        values.append(run_id)
        with connect(self._store) as connection:
            connection.execute(
                "UPDATE summary_runs SET " + ", ".join(pairs) + " WHERE id=%s",
                tuple(values),
            )
            connection.commit()
        return self.get_run(run_id)

    def save_evidence(
        self, run_id: str, workflow_id: str, step_key: str,
        records: List[dict],
    ) -> str:
        evidence_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_EVIDENCE,
                (
                    evidence_id, run_id, workflow_id, step_key, Jsonb(records),
                ),
            )
            connection.commit()
        return evidence_id

    def run_evidence(self, run_id: str) -> List[dict]:
        return self._all("""
            SELECT id, workflow_id, step_key, records, created_at
            FROM summary_evidence WHERE run_id=%s ORDER BY created_at
        """, (run_id,))

    def evidence_catalog(self, run_id: str) -> List[dict]:
        """Lightweight evidence metadata for the drawer's collapsed rows."""
        return self._all("""
            SELECT id, workflow_id, step_key,
                   jsonb_array_length(records) AS row_count, created_at
            FROM summary_evidence WHERE run_id=%s ORDER BY created_at
        """, (run_id,))

    def conversation_runs(self, conversation_id: str) -> List[dict]:
        """Every finished run of a conversation, oldest first.

        Citations are resolved across the thread, not within one run: a
        follow-up cites what an earlier turn said. Only finished runs carry a
        `result`, so only those can hold citations at all.
        """
        return self._all("""
            SELECT id, conversation_id, question, result, status, created_at
            FROM summary_runs
            WHERE conversation_id=%s AND status IN ('completed','partial')
            ORDER BY created_at
        """, (conversation_id,))

    def evidence_record(
        self, run_id: str, evidence_id: str, limit: int = 100
    ) -> dict:
        """One evidence row, bounded, for resolving a citation.

        Scoped by `run_id` as well as `evidence_id` so a caller who has passed
        the run's ownership check cannot reach another run's evidence by
        guessing an id — the same pairing `evidence_page` already relies on.
        """
        return self.evidence_page(run_id, evidence_id, 0, limit)

    def evidence_page(
        self, run_id: str, evidence_id: str, offset: int, limit: int
    ) -> dict:
        """Return only the requested JSONB array positions, in stable order."""
        row = self._one("""
            SELECT evidence.id, evidence.workflow_id, evidence.step_key,
                   jsonb_array_length(evidence.records) AS row_count,
                   evidence.created_at,
                   (
                       SELECT COALESCE(
                           jsonb_agg(evidence.records -> position
                                     ORDER BY position),
                           '[]'::jsonb
                       )
                       FROM generate_series(
                           %s,
                           LEAST(
                               %s,
                               jsonb_array_length(evidence.records) - 1
                           )
                       ) AS position
                   ) AS records
            FROM summary_evidence AS evidence
            WHERE evidence.run_id=%s AND evidence.id=%s
        """, (offset, offset + limit - 1, run_id, evidence_id))
        row["offset"] = offset
        row["limit"] = limit
        row["has_more"] = offset + len(row["records"]) < row["row_count"]
        return row


def _empty_progress() -> dict:
    return {"completed": 0, "total": 0, "sections": []}


def _run_changes(changes: dict):
    allowed = {"status", "progress", "result", "error", "finished_at"}
    pairs, values = [], []
    for key, value in changes.items():
        if key in allowed:
            pairs.append(key + "=%s")
            values.append(
                Jsonb(value) if key in {"progress", "result"} else value
            )
    return pairs, values


_INSERT_RUN = """
    INSERT INTO summary_runs (
        id, conversation_id, kind, question, skill_keys, agent_keys,
        status, progress
    ) VALUES (%s,%s,%s,%s,%s,%s,'queued',%s)
"""

_INSERT_EVIDENCE = """
    INSERT INTO summary_evidence (
        id, run_id, workflow_id, step_key, records
    ) VALUES (%s,%s,%s,%s,%s)
"""
