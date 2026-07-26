"""The only PostgreSQL repository: schema, catalog, workflows, runs, evidence."""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from psycopg.types.json import Jsonb

from app.common.errors import NotFoundError
from app.dal.database.postgres import connect

_KEY_RE = re.compile(r"[^a-z0-9_-]+")


def _id() -> str:
    return str(uuid.uuid4())


def _key(value: str) -> str:
    result = _KEY_RE.sub("-", value.strip().lower()).strip("-")
    return result or _id()


class Repository:
    def __init__(self, settings_store):
        self._store = settings_store

    def initialize(self) -> None:
        with connect(self._store) as connection:
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute(
                "DELETE FROM conversations WHERE expires_at <= NOW()"
            )
            connection.commit()
        self._seed_agent_content()

    def health(self) -> dict:
        with connect(self._store) as connection:
            connection.execute("SELECT 1").fetchone()
        return {"database": "ok"}

    def list_packages(self) -> List[dict]:
        return self._all("""
            SELECT DISTINCT ON (package_key) *
            FROM summary_packages
            ORDER BY package_key, version DESC
        """)

    def get_package(self, version_id: str) -> dict:
        return self._one(
            "SELECT * FROM summary_packages WHERE id=%s", (version_id,)
        )

    def create_package(self, data: dict) -> dict:
        package_key = data.get("package_key") or _key(data["name"])
        version = self._next_version("summary_packages", "package_key", package_key)
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_packages (
                    id, package_key, version, name, description, package_id,
                    input_cube_name, input_cube_parameter, input_mode,
                    output_cube_name, query_name, timeout_seconds,
                    example_input, example_output
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
            """, (
                row_id, package_key, version, data["name"],
                data.get("description", ""), str(data["package_id"]),
                data["input_cube_name"], data["input_cube_parameter"],
                data.get("input_mode", "single"), data["output_cube_name"],
                data.get("query_name", ""), data.get("timeout_seconds"),
                Jsonb(data.get("example_input", [])),
                Jsonb(data.get("example_output", [])),
            ))
            connection.commit()
        return self.get_package(row_id)

    def list_workflows(self) -> List[dict]:
        rows = self._all("""
            SELECT DISTINCT ON (workflow_key) *
            FROM summary_workflows
            ORDER BY workflow_key, version DESC
        """)
        for row in rows:
            row["steps"] = self._steps(row["id"])
        return rows

    def get_workflow(self, version_id: str) -> dict:
        row = self._one(
            "SELECT * FROM summary_workflows WHERE id=%s", (version_id,)
        )
        row["steps"] = self._steps(version_id)
        return row

    def create_workflow(self, data: dict) -> dict:
        workflow_key = data.get("workflow_key") or _key(data["name"])
        version = self._next_version(
            "summary_workflows", "workflow_key", workflow_key
        )
        row_id = _id()
        self._validate_steps(data.get("steps", []))
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_workflows (
                    id, workflow_key, version, name, description, role,
                    status, system_prompt, output_schema, examples
                ) VALUES (%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s)
            """, (
                row_id, workflow_key, version, data["name"],
                data.get("description", ""), data.get("role", "detail"),
                data.get("system_prompt", ""),
                Jsonb(data.get("output_schema", {})),
                Jsonb(data.get("examples", [])),
            ))
            for position, step in enumerate(data.get("steps", [])):
                connection.execute("""
                    INSERT INTO workflow_steps (
                        id, workflow_id, position, step_key, name,
                        package_version_id, depends_on, input_source,
                        input_field, summary_prompt
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    _id(), row_id, position, step["key"], step["name"],
                    step["package_version_id"],
                    Jsonb(step.get("depends_on", [])),
                    step.get("input_source", "workflow.id"),
                    step.get("input_field", ""),
                    step.get("summary_prompt", ""),
                ))
            connection.commit()
        return self.get_workflow(row_id)

    def publish_workflow(self, version_id: str) -> dict:
        workflow = self.get_workflow(version_id)
        self._validate_for_publish(workflow)
        with connect(self._store) as connection:
            connection.execute("""
                UPDATE summary_workflows
                SET status='archived'
                WHERE workflow_key=%s AND status='published'
            """, (workflow["workflow_key"],))
            connection.execute("""
                UPDATE summary_workflows
                SET status='published', published_at=NOW()
                WHERE id=%s
            """, (version_id,))
            connection.commit()
        return self.get_workflow(version_id)

    def published_workflows(self, roles: List[str]) -> List[dict]:
        rows = self._all("""
            SELECT * FROM summary_workflows
            WHERE status='published' AND role = ANY(%s)
            ORDER BY name
        """, (roles,))
        for row in rows:
            row["steps"] = self._steps(row["id"])
        return rows

    def list_agent_content(self) -> List[dict]:
        return self._all("""
            SELECT DISTINCT ON (content_key) *
            FROM agent_content
            ORDER BY content_key, version DESC
        """)

    def create_agent_content(self, data: dict) -> dict:
        content_key = data.get("content_key") or _key(data["name"])
        version = self._next_version("agent_content", "content_key", content_key)
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO agent_content (
                    id, content_key, version, kind, name, description,
                    content, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'draft')
            """, (
                row_id, content_key, version, data["kind"], data["name"],
                data.get("description", ""), data["content"],
            ))
            connection.commit()
        return self._one("SELECT * FROM agent_content WHERE id=%s", (row_id,))

    def publish_agent_content(self, version_id: str) -> dict:
        item = self._one("SELECT * FROM agent_content WHERE id=%s", (version_id,))
        with connect(self._store) as connection:
            connection.execute("""
                UPDATE agent_content SET status='archived'
                WHERE content_key=%s AND status='published'
            """, (item["content_key"],))
            connection.execute("""
                UPDATE agent_content SET status='published', published_at=NOW()
                WHERE id=%s
            """, (version_id,))
            connection.commit()
        return self._one("SELECT * FROM agent_content WHERE id=%s", (version_id,))

    def published_content(self, key: str, fallback: str) -> str:
        rows = self._all("""
            SELECT content FROM agent_content
            WHERE content_key=%s AND status='published'
            ORDER BY version DESC LIMIT 1
        """, (key,))
        return rows[0]["content"] if rows else fallback

    def create_conversation(self, session_id: str, root_id: str) -> dict:
        row_id = _id()
        retention = self._store.get().conversation_retention_days
        expires = datetime.now(timezone.utc) + timedelta(days=retention)
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO conversations (id, session_id, root_id, expires_at)
                VALUES (%s,%s,%s,%s)
            """, (row_id, session_id, root_id, expires))
            connection.commit()
        return self.get_conversation(row_id, session_id)

    def get_conversation(self, conversation_id: str, session_id=None) -> dict:
        params = [conversation_id]
        condition = "id=%s"
        if session_id:
            condition += " AND session_id=%s"
            params.append(session_id)
        row = self._one(
            "SELECT * FROM conversations WHERE " + condition, tuple(params)
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

    def create_run(self, conversation_id: str, question: str, kind: str) -> dict:
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_runs (
                    id, conversation_id, kind, question, status, progress
                ) VALUES (%s,%s,%s,%s,'queued',%s)
            """, (
                row_id, conversation_id, kind, question,
                Jsonb({"completed": 0, "total": 0, "sections": []}),
            ))
            connection.execute(
                "UPDATE conversations SET updated_at=NOW() WHERE id=%s",
                (conversation_id,),
            )
            connection.commit()
        return self.get_run(row_id)

    def get_run(self, run_id: str) -> dict:
        return self._one("SELECT * FROM summary_runs WHERE id=%s", (run_id,))

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
        allowed = {"status", "progress", "result", "error", "finished_at"}
        pairs, values = [], []
        for key, value in changes.items():
            if key not in allowed:
                continue
            pairs.append(key + "=%s")
            values.append(Jsonb(value) if key in {"progress", "result"} else value)
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
        self, run_id: str, workflow_id: str, step_key: str, records: List[dict]
    ) -> str:
        evidence_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_evidence (
                    id, run_id, workflow_id, step_key, records
                ) VALUES (%s,%s,%s,%s,%s)
            """, (
                evidence_id, run_id, workflow_id, step_key, Jsonb(records),
            ))
            connection.commit()
        return evidence_id

    def run_evidence(self, run_id: str) -> List[dict]:
        return self._all("""
            SELECT id, workflow_id, step_key, records, created_at
            FROM summary_evidence WHERE run_id=%s ORDER BY created_at
        """, (run_id,))

    def save_feedback(self, session_id: str, data: dict) -> dict:
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_feedback (
                    id, run_id, session_id, rating, comment
                ) VALUES (%s,%s,%s,%s,%s)
            """, (
                row_id, data["run_id"], session_id, data["rating"],
                data.get("comment", ""),
            ))
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

    def _seed_agent_content(self) -> None:
        for item in _SEED_CONTENT:
            exists = self._all(
                "SELECT id FROM agent_content WHERE content_key=%s LIMIT 1",
                (item["content_key"],),
            )
            if not exists:
                created = self.create_agent_content(item)
                self.publish_agent_content(created["id"])

    def _steps(self, workflow_id: str) -> List[dict]:
        return self._all("""
            SELECT
                id, workflow_id, position, step_key AS key, name,
                package_version_id, depends_on, input_source, input_field,
                summary_prompt
            FROM workflow_steps
            WHERE workflow_id=%s ORDER BY position
        """, (workflow_id,))

    def _next_version(self, table: str, key_name: str, key_value: str) -> int:
        with connect(self._store) as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM %s WHERE %s=%%s"
                % (table, key_name),
                (key_value,),
            ).fetchone()
        return int(row["version"]) + 1

    def _one(self, query: str, params=()) -> dict:
        rows = self._all(query, params)
        if not rows:
            raise NotFoundError("הפריט לא נמצא")
        return rows[0]

    def _all(self, query: str, params=()) -> List[dict]:
        with connect(self._store) as connection:
            rows = connection.execute(query, params).fetchall()
            connection.commit()
        return [dict(row) for row in rows]

    @staticmethod
    def _validate_steps(steps: List[dict]) -> None:
        keys = [step["key"] for step in steps]
        if len(keys) != len(set(keys)):
            raise ValueError("מפתחות השלבים חייבים להיות ייחודיים")
        seen = set()
        for step in steps:
            missing = set(step.get("depends_on", [])) - seen
            if missing:
                raise ValueError(
                    "שלב תלוי בשלב מאוחר או לא קיים: " + ", ".join(missing)
                )
            source = step.get("input_source", "workflow.id")
            if source != "workflow.id":
                parts = source.split(".")
                if (
                    len(parts) != 2 or parts[0] != "steps"
                    or parts[1] not in seen
                ):
                    raise ValueError("מקור הקלט חייב להיות שלב מוקדם יותר")
                if not step.get("input_field", "").strip():
                    raise ValueError("נדרש שדה פלט למיפוי משלב קודם")
            seen.add(step["key"])

    def _validate_for_publish(self, workflow: dict) -> None:
        if not workflow["steps"]:
            raise ValueError("אי אפשר לפרסם תהליך ללא שלבים")
        self._validate_steps(workflow["steps"])
        has_workflow_examples = bool(workflow.get("examples"))
        packages_have_examples = all(
            bool(package.get("example_input"))
            and bool(package.get("example_output"))
            for package in (
                self.get_package(step["package_version_id"])
                for step in workflow["steps"]
            )
        )
        if not has_workflow_examples and not packages_have_examples:
            raise ValueError(
                "נדרשת דוגמת תהליך או דוגמאות קלט ופלט לכל חבילה לפני פרסום"
            )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS summary_packages (
    id TEXT PRIMARY KEY,
    package_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    package_id TEXT NOT NULL,
    input_cube_name TEXT NOT NULL,
    input_cube_parameter TEXT NOT NULL,
    input_mode TEXT NOT NULL CHECK (input_mode IN ('single','many')),
    output_cube_name TEXT NOT NULL,
    query_name TEXT NOT NULL DEFAULT '',
    timeout_seconds INTEGER,
    example_input JSONB NOT NULL DEFAULT '[]',
    example_output JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(package_key, version)
);

CREATE TABLE IF NOT EXISTS summary_workflows (
    id TEXT PRIMARY KEY,
    workflow_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('baseline','detail','both')),
    status TEXT NOT NULL CHECK (status IN ('draft','published','archived')),
    system_prompt TEXT NOT NULL DEFAULT '',
    output_schema JSONB NOT NULL DEFAULT '{}',
    examples JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE(workflow_key, version)
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES summary_workflows(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    step_key TEXT NOT NULL,
    name TEXT NOT NULL,
    package_version_id TEXT NOT NULL REFERENCES summary_packages(id),
    depends_on JSONB NOT NULL DEFAULT '[]',
    input_source TEXT NOT NULL DEFAULT 'workflow.id',
    input_field TEXT NOT NULL DEFAULT '',
    summary_prompt TEXT NOT NULL DEFAULT '',
    UNIQUE(workflow_id, step_key)
);

CREATE TABLE IF NOT EXISTS agent_content (
    id TEXT PRIMARY KEY,
    content_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('skill','prompt')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft','published','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE(content_key, version)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    root_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS summary_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('full','follow_up')),
    question TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (
        status IN ('queued','running','completed','partial','failed')
    ),
    progress JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS summary_evidence (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES summary_runs(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    step_key TEXT NOT NULL,
    records JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS summary_feedback (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES summary_runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating IN (-1,1)),
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversations_session_idx
    ON conversations(session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS runs_conversation_idx
    ON summary_runs(conversation_id, created_at);
"""


_SEED_CONTENT = [
    {
        "content_key": "build-summary-workflow",
        "kind": "skill",
        "name": "בניית תהליך סיכום",
        "description": "מסייע ל-FDE לבנות תהליך מחבילות FLAPI.",
        "content": """# בניית תהליך סיכום

ראיין את ה-FDE החלטה אחת בכל פעם. הגדר מזהה קלט כמחרוזת, בחר חבילות
מהקטלוג, חבר פלטים לקלטים, סמן תלות ו-fan-out, והגדר חוזה פלט וראיות.
צור טיוטה בלבד. אל תפרסם אוטומטית.""",
    },
    {
        "content_key": "test-summary-workflow",
        "kind": "skill",
        "name": "בדיקת תהליך סיכום",
        "description": "מריץ דוגמאות ובודק מיפויים, עובדות וראיות.",
        "content": """# בדיקת תהליך סיכום

בדוק שכל מיפוי מפנה לקלט או לפלט מוקדם, שכל מזהה נשאר מחרוזת, ושכל
עובדה צפויה נתמכת בראיה. דווח כשלים קריטיים וחסום פרסום עד תיקונם.""",
    },
    {
        "content_key": "diagnose-summary-workflow",
        "kind": "skill",
        "name": "אבחון תהליך סיכום",
        "description": "מפריד בין כשל חבילה, מיפוי, תהליך והנחיה.",
        "content": """# אבחון תהליך סיכום

התחל מה-trace ומהראיות. סווג את שורש התקלה כחיבור FLAPI, קלט, מיפוי,
חוזה פלט, skill או prompt. הצע גרסת טיוטה חדשה ושמור את הגרסה שפורסמה.""",
    },
    {
        "content_key": "final-summary",
        "kind": "prompt",
        "name": "סיכום מלא",
        "description": "הנחיית ברירת מחדל לחיבור כל חלקי הסיכום.",
        "content": """כתוב בעברית סיכום עובדתי ומובן על המזהה. החזר JSON עם
summary, key_findings, risks, missing_data ו-suggested_questions.
השתמש רק בעובדות ובראיות שסופקו. ציין כיסוי חלקי ואל תנחש.""",
    },
    {
        "content_key": "follow-up-router",
        "kind": "prompt",
        "name": "ניתוב שאלת המשך",
        "description": "בוחר תהליך detail שפורסם או משתמש בראיות קיימות.",
        "content": """בחר workflow_key אחד רק אם הראיות הקיימות אינן מספיקות.
אם כמה תהליכים מתאימים החזר clarification. אל תמציא כלי או תהליך.""",
    },
]
