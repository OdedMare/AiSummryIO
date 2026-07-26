"""Summary run progress and evidence persistence."""

from typing import List

from psycopg.types.json import Jsonb

from app.dal.database.postgres import connect
from app.dal.repository.base import new_id


class RunRepository:
    def create_run(
        self, conversation_id: str, question: str, kind: str, skill_keys=None
    ) -> dict:
        row_id = new_id()
        with connect(self._store) as connection:
            connection.execute(
                _INSERT_RUN,
                (
                    row_id, conversation_id, kind, question,
                    Jsonb(skill_keys or []), Jsonb(_empty_progress()),
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at=NOW() WHERE id=%s",
                (conversation_id,),
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
        id, conversation_id, kind, question, skill_keys, status, progress
    ) VALUES (%s,%s,%s,%s,%s,'queued',%s)
"""

_INSERT_EVIDENCE = """
    INSERT INTO summary_evidence (
        id, run_id, workflow_id, step_key, records
    ) VALUES (%s,%s,%s,%s,%s)
"""
