"""The only PostgreSQL repository: schema, catalog, workflows, runs, evidence."""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from psycopg.types.json import Jsonb

from app.common.errors import NotFoundError
from app.dal.database.postgres import connect, ensure_schema

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
        # The schema must exist before any CREATE TABLE resolves into it.
        ensure_schema(self._store)
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

    def agent_tools(self) -> List[dict]:
        return self._all("""
            SELECT * FROM (
                SELECT DISTINCT ON (package_key) *
                FROM summary_packages
                ORDER BY package_key, version DESC
            ) AS latest
            WHERE agent_enabled IS TRUE
            ORDER BY name
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
                    agent_enabled, agent_instructions,
                    output_schema, example_input, example_output
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
            """, (
                row_id, package_key, version, data["name"],
                data.get("description", ""), str(data["package_id"]),
                data["input_cube_name"], data["input_cube_parameter"],
                data.get("input_mode", "single"), data["output_cube_name"],
                data.get("query_name", ""), data.get("timeout_seconds"),
                data.get("agent_enabled", True),
                data.get("agent_instructions", ""),
                Jsonb(data.get("output_schema", {})),
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

    def create_agent_content(self, data: dict) -> dict:
        content_key = data.get("content_key") or _key(data["name"])
        version = self._next_version("agent_content", "content_key", content_key)
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO agent_content (
                    id, content_key, version, kind, name, description,
                    content, user_selectable, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')
            """, (
                row_id, content_key, version, data["kind"], data["name"],
                data.get("description", ""), data["content"],
                data.get("user_selectable", False),
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

    def create_conversation(
        self, session_id: str, root_id: str, boundaries=None
    ) -> dict:
        row_id = _id()
        retention = self._store.get().conversation_retention_days
        expires = datetime.now(timezone.utc) + timedelta(days=retention)
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO conversations
                    (id, session_id, root_id, boundaries, expires_at)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                row_id, session_id, root_id,
                Jsonb(boundaries) if boundaries else None, expires,
            ))
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

    def create_run(
        self, conversation_id: str, question: str, kind: str,
        skill_keys=None,
    ) -> dict:
        row_id = _id()
        with connect(self._store) as connection:
            connection.execute("""
                INSERT INTO summary_runs (
                    id, conversation_id, kind, question, skill_keys,
                    status, progress
                ) VALUES (%s,%s,%s,%s,%s,'queued',%s)
            """, (
                row_id, conversation_id, kind, question,
                Jsonb(skill_keys or []),
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
                if parts[1] not in set(step.get("depends_on", [])):
                    raise ValueError(
                        "שלב הקורא מפלט שלב אחר חייב להצהיר עליו בתלויות: "
                        + parts[1]
                    )
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
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    agent_instructions TEXT NOT NULL DEFAULT '',
    output_schema JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(package_key, version)
);

ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS agent_instructions TEXT NOT NULL DEFAULT '';
ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS output_schema JSONB NOT NULL DEFAULT '{}';

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
    user_selectable BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL CHECK (status IN ('draft','published','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE(content_key, version)
);

ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS user_selectable BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    root_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS boundaries JSONB;

CREATE TABLE IF NOT EXISTS summary_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('full','follow_up')),
    question TEXT NOT NULL DEFAULT '',
    skill_keys JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (
        status IN ('queued','running','completed','partial','failed')
    ),
    progress JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

ALTER TABLE summary_runs
    ADD COLUMN IF NOT EXISTS skill_keys JSONB NOT NULL DEFAULT '[]';

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
        "content": """# Build a summary workflow

Guide the FDE through building one workflow. Ask about one decision at a
time; never combine two questions into one sentence.

**Language:** the FDE writes in Hebrew and reads Hebrew. Ask your questions
and write every explanation, step name, and prompt in Hebrew. Keep field
names, keys, and identifiers exactly as they are — never translate
`workflow.id`, `depends_on`, a `package_version_id`, or a step key.

## Order of inquiry
1. **What does the user get at the end?** State the summary product before
   picking any package.
2. **What is the incoming identifier?** Always a string. `00123` stays
   `00123` and is never turned into 123.
3. **Which catalog packages provide that?** Only what exists. Never invent
   a package, an HTTP call, or SQL.
4. **What is the step order?** Steps that depend on nothing come first;
   steps consuming another step's output come after it.
5. **How does each step get its input?** Exactly one of `workflow.id`,
   `workflow.boundaries`, or `steps.<key>` plus an `input_field` naming a
   field that really appears in that step's example output.
6. **What is the workflow role?** `baseline` always runs; `detail` runs only
   on a follow-up question; `both` runs in both cases.

## The mapping rule that fails most often
A step reading another step's output must BOTH declare it in `depends_on`
AND point at a field present in the example output. A mapping to a field
that is not in the example will be rejected at publish time. Verify the
field name against the package's `example_output` — never from memory.

## input_mode
`single` — the package takes one identifier; it is called once per
identifier. `many` — all identifiers go in a single call. Choose according
to what the package actually supports, not what is convenient.

## Before finishing
Confirm every step has a Hebrew name a user would understand, and that the
output contract ADDS fields on top of
`summary`/`facts`/`warnings`/`suggested_questions` rather than replacing
them.

Produce a draft only. Never publish automatically.""",
    },
    {
        "content_key": "test-summary-workflow",
        "kind": "skill",
        "name": "בדיקת תהליך סיכום",
        "description": "מריץ דוגמאות ובודק מיפויים, עובדות וראיות.",
        "content": """# Test a summary workflow

Verify a draft before it is published, and report what would break.

**Language:** report every finding in Hebrew, because the FDE reads Hebrew.
Keep field names, step keys, and identifiers untranslated inside the text.

## Check in this order — stop at the first blocking failure
1. **Identifier integrity.** The identifier stays a string end to end. A
   leading zero that disappears is a blocking failure, not a warning.
2. **Mappings.** Every `input_source` is `workflow.id`,
   `workflow.boundaries`, or a `steps.<key>` that refers to an EARLIER
   step. Every `steps.<key>` reference is also declared in `depends_on`.
3. **Field existence.** Every `input_field` names a field that appears in
   the referenced step's example output. A missing field is blocking.
4. **Examples.** Each package has both an example input and an example
   output, or the workflow itself has an example. Publishing is blocked
   otherwise.
5. **Evidence support.** Each fact the summary is expected to state can be
   traced to a package output field. A fact with no possible source means
   the prompt is inviting the model to guess.
6. **Boundaries.** If any step uses `workflow.boundaries`, confirm the
   failure message is clear when no area was drawn.

## Severity — do not blur these
- **Blocking**: coerced identifiers, invalid mappings, missing fields,
  missing mandatory examples. These must stop publishing.
- **Warning**: thin coverage, a step likely to return zero rows, a vague
  step name. These are reported but do not block.

## Output
State which checks passed, then list blocking failures first with the exact
step and field involved, and what to change. If everything passes, say so
plainly and state what the dry run actually exercised.""",
    },
    {
        "content_key": "diagnose-summary-workflow",
        "kind": "skill",
        "name": "אבחון תהליך סיכום",
        "description": "מפריד בין כשל חבילה, מיפוי, תהליך והנחיה.",
        "content": """# Diagnose a summary workflow

Find the root cause of a bad or failed run, and separate a data problem
from a wiring problem from a prompting problem.

**Language:** write the diagnosis in Hebrew. Keep step keys, field names,
and error strings verbatim so they can be searched.

## Start from the evidence, not from the summary
Read the trace and the stored evidence rows first. The Hebrew summary is
the LAST place to look — it reflects every upstream problem and will
mislead you about which one occurred.

## Classify the root cause into exactly one of these
- **FLAPI connection** — timeouts, auth, TLS, package not found. The step
  returned no rows and recorded an error. Nothing downstream is meaningful.
- **Input** — the package ran but the identifier was wrong, empty, or a
  drawn area was missing. Zero rows with no error usually lands here.
- **Mapping** — a later step read the wrong field, or read a field that is
  always empty. Look for a step whose input list is empty while the
  previous step returned rows.
- **Output contract** — rows arrived but the schema did not describe them,
  so fields were dropped or landed under `section.fields`.
- **Skill or prompt** — the data is correct and complete, but the wording
  of the summary is wrong, hedged, or invents claims. Only conclude this
  after ruling out all four above.

## The distinction that matters most
"Zero rows" and "the step failed" are different diagnoses with different
fixes. Check whether a warning was recorded for the step before deciding.
A partial run keeps its successful sections — do not report the whole
workflow as broken when one package failed.

## Output
Name the single root cause, show the evidence that points to it, and
propose a new DRAFT version with the specific change. Never modify the
published version; it stays immutable.""",
    },
    {
        "content_key": "summary-executive",
        "kind": "skill",
        "name": "תקציר מנהלים",
        "description": "התמונה החשובה ביותר, קצר וללא מונחים טכניים.",
        "user_selectable": True,
        "content": """# Executive brief

## What you produce
One paragraph answering "what matters right now", followed by 3-5 decisive
points.

**Language:** the summary sections you receive are in Hebrew, and your
output must be in Hebrew. Do not translate names, places, or identifiers.

## Method
1. Scan every summary section and mark the facts with the largest impact.
2. Rank by impact on a decision — not by order of appearance, not by how
   many records a section returned.
3. Merge facts that say the same thing into one point. Never repeat a fact.
4. Open with the strongest finding. Never open by describing the process or
   what was searched.

## Evidence rules
- Every point rests on a fact from the summary sections. No inference
  beyond the data.
- A number, date, or name appears only if it is written in the source.
- Partial coverage or missing information is stated openly, never hidden.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the paragraph. `items` = the points, each standing on its own.

## Worked example
Facts: "הנכס נרשם ב-2019 על שם דנה כהן"; "קיים שעבוד פעיל מ-2021";
"בקשת היתר מ-2023 סורבה".
`summary`: "הנכס בבעלות דנה כהן משנת 2019, אך שני חסמים פעילים משפיעים על
שימוש בו: שעבוד מ-2021 ובקשת היתר שסורבה ב-2023."
`items`: ["שעבוד פעיל מ-2021 מגביל עסקאות", "בקשת היתר סורבה ב-2023",
"הבעלות עצמה רשומה ואינה במחלוקת"]

## Do not
No package jargon or field names. No recommended actions — a separate
Skill owns those. Do not write "no information found" as a point when
other facts exist.""",
    },
    {
        "content_key": "summary-risks",
        "kind": "skill",
        "name": "סיכונים ודגלים אדומים",
        "description": "מזהה חריגות, סתירות וחוסרים שדורשים תשומת לב.",
        "user_selectable": True,
        "content": """# Risks and red flags

## What you produce
A severity-ranked risk list. For each: what was found, the impact, what to
check.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep names and identifiers exactly as written.

## Method — scan for these four categories in this order
1. **Contradiction** — two sections state things that cannot both be true.
2. **Anomaly** — a value outside the expected range, a future date,
   duplicate records.
3. **Active blocker** — a lien, restriction, refusal, or open proceeding.
4. **Critical gap** — a key field empty or a package that failed, where the
   absence itself changes a conclusion.

Rank by severity: what affects a decision now comes before what merely
needs verification.

## The distinction you must never blur
Missing information is not a proven risk. "לא נמצא רישום שעבוד" is neither
"there is no lien" nor "there is a lien". Frame it as a gap requiring a
check, and say what that check would settle.

## Evidence rules
- Every risk points at the fact that produced it.
- No probability estimates and no invented severity that the data does not
  support.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the overall risk picture in one or two sentences.
`items` = one risk per line, shaped as
"what was found — possible impact — what to check".

## Worked example
Facts: "בעלות רשומה על שם דנה כהן"; "עסקת מכר נרשמה ב-2022 לטובת אבי לוי";
"לא נמצאה רשומת שעבוד".
`items`: [
"סתירה בבעלות: הרישום על שם דנה כהן אך נרשמה עסקת מכר לאבי לוי ב-2022 —
עלול לפגוע בתוקף עסקה — לבדוק איזה רישום מעודכן",
"לא נמצאה רשומת שעבוד — ייתכן שאין שעבוד וייתכן שהחבילה לא כיסתה זאת —
לאמת מול מקור השעבודים לפני הסתמכות"
]

## If there is no risk
Say so explicitly in `summary` and return an empty `items`. Never invent a
risk to fill the list.""",
    },
    {
        "content_key": "summary-actions",
        "kind": "skill",
        "name": "צעדים מומלצים",
        "description": "הופך את הממצאים לרשימת פעולות ברורה ומעשית.",
        "user_selectable": True,
        "content": """# Recommended actions

## What you produce
A ranked action list someone could execute tomorrow morning.

**Language:** input sections are Hebrew and your output must be Hebrew.
Start each action with a Hebrew verb.

## Method
1. For each finding ask: does this require action, or is it background?
   Only the former becomes an item.
2. Phrase every action with the verb first: "לאמת", "לפנות", "לעדכן",
   "לעצור".
3. Rank by what unblocks the rest: an action that enables other actions
   comes first.
4. If a finding needs information that does not exist yet, the action IS
   obtaining that information.

## What makes an action good
- **Executable**: it says who to contact or what to check — not "to
  consider" or "to examine".
- **Connected**: you can point at the fact that produced it.
- **Specific**: "לאמת מול מקור השעבודים", not "לוודא שהכל תקין".

## Evidence rules
- Each action follows from a supplied fact. Never assert new facts.
- Never recommend an action requiring information absent from the summary;
  recommend obtaining it first.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the single most important next step, in one sentence.
`items` = one action per line, shaped as "what to do — why".

## Worked example
Facts: "סתירה בין רישום בעלות לעסקת מכר מ-2022"; "לא נמצאה רשומת שעבוד".
`summary`: "לפני כל החלטה יש להכריע איזה רישום בעלות מעודכן."
`items`: [
"לאמת מול לשכת הרישום איזה רישום בעלות תקף — סתירה בין שני מקורות חוסמת
כל עסקה",
"לבקש אישור העדר שעבודים ממקור מוסמך — הסיכום לא כיסה שעבודים ולכן אין
להסיק שאין"
]

## If nothing warrants action
Say in `summary` that the findings require no action, and use `items` to
state which information would change that answer. Never invent actions to
fill a list.""",
    },
    {
        "content_key": "summary-timeline",
        "kind": "skill",
        "name": "ציר זמן",
        "description": "מסדר אירועים ותאריכים לפי סדר כרונולוגי.",
        "user_selectable": True,
        "content": """# Timeline

## What you produce
A sequence of events, oldest to newest, showing how the identifier reached
its current state.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep dates in the format they appear in the source.

## Method
1. Collect from every section each fact carrying a date or an explicit
   ordering.
2. Sort oldest to newest. A partial date (year only) is kept as-is and
   marked as partial.
3. If two events share a date, keep both and impose no order between them.
4. Finally, if the sequence reveals a gap or a chronological contradiction,
   state it in `summary`.

## What belongs and what does not
- **Belongs**: an event with a date, or with explicit ordering ("לאחר",
  "קדם ל").
- **Does not**: an ongoing state with no date, and any fact whose position
  you would have to guess.

## Evidence rules
- Never guess a date and never derive one from context.
- Never impose a chronological order the data does not support.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = what the sequence shows, including chronological gaps.
`items` = one event per line, shaped as "date — what happened — source".

## Worked example
Facts: "הנכס נרשם ב-2019"; "שעבוד נרשם ב-2021"; "בקשת היתר סורבה 2023";
"הבעלים מתגורר בכתובת" (no date).
`summary`: "שלושה אירועים בין 2019 ל-2023, ברצף עקבי: רישום, שעבוד, סירוב
היתר. עובדת המגורים ללא תאריך ולכן אינה בציר."
`items`: ["2019 — הנכס נרשם על שם דנה כהן — בעלות",
"2021 — נרשם שעבוד פעיל — שעבודים",
"2023 — בקשת היתר סורבה — היתרים"]

## If there is no time data
Say so explicitly in `summary` and return an empty `items`. Never build a
timeline from guesses.""",
    },
    {
        "content_key": "summary-contradictions",
        "kind": "skill",
        "name": "סתירות בין מקורות",
        "description": "משווה מקורות ומצביע היכן הם אינם מסכימים.",
        "user_selectable": True,
        "content": """# Contradictions between sources

## What you produce
A list of disagreements between summary sections, and what would settle
each one.

**Language:** input sections are Hebrew and your output must be Hebrew.
Quote conflicting values exactly as they appear.

## Method
1. Find fields appearing in more than one section: name, date, status,
   address, amount.
2. For each such field, compare the values across sections.
3. Classify every difference into one of the four categories below — the
   classification is the substance of this Skill.
4. For each real contradiction, say what would settle it: which source,
   which document, which check.

## Classify differences — not every difference is a contradiction
- **Contradiction**: two values that cannot both be true. This is what
  gets reported.
- **Timing difference**: both sources correct at different times. Say it is
  timing.
- **Resolution difference**: "תל אביב" vs "תל אביב, רוטשילד 5" —
  complementary, not conflicting.
- **Wording difference**: same content, different words. Not reported at
  all.

## Evidence rules
- Point precisely at both sections and both conflicting values.
- Never decide who is right when the data cannot settle it; say what would.
- A field present in one section and absent in another is NOT a
  contradiction — that is a coverage gap.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = whether the sources are consistent, and the most significant
contradiction if any.
`items` = shaped as
"field — source A says X, source B says Y — type — what would settle it".

## Worked example
Facts: section "בעלות": "הבעלים דנה כהן, עדכון 2019"; section "עסקאות":
"נרשמה עסקת מכר לאבי לוי ב-2022"; section "כתובות": "תל אביב" vs
"תל אביב רוטשילד 5".
`summary`: "סתירה אחת ממשית בזהות הבעלים, ובנוסף הפרש רזולוציה בכתובת."
`items`: [
"בעלים — בעלות אומרת דנה כהן (2019), עסקאות אומרות אבי לוי (2022) —
סתירה — לבדוק בלשכת הרישום איזה רישום תקף כיום",
"כתובת — כתובות אומר תל אביב מול תל אביב רוטשילד 5 — הפרש רזולוציה —
אין צורך בהכרעה, הערך המפורט מכיל את הכללי"
]

## If there are no contradictions
Say in `summary` that the sources agree on their shared fields, and return
an empty `items`.""",
    },
    {
        "content_key": "summary-entities",
        "kind": "skill",
        "name": "גורמים וקשרים",
        "description": "ממפה מי ומה מופיע בסיכום ואיך הם מקושרים.",
        "user_selectable": True,
        "content": """# Entities and relationships

## What you produce
A map of the parties around the identifier: who appears, in what role, and
what connects them to it.

**Language:** input sections are Hebrew and your output must be Hebrew.
Reproduce every name exactly as written — never normalize or translate it.

## Method
1. Collect every named entity from the sections: people, companies,
   authorities, properties, identifiers.
2. For each, determine its role FROM THE DATA ONLY — owner, applicant,
   issuer, neighbor, creditor.
3. Describe its relationship to the main identifier, and relationships
   between entities where the source states them.
4. Present entities with the tightest connection to the identifier first.

## Evidence rules
- Never merge two similar names into one entity. If they might be the same,
  say so as a possibility and keep them separate.
- Never infer a role that is not stated. "מופיע ברשומת שעבוד" is not
  "creditor" unless the source says so.
- Never invent a relationship between two entities merely because they
  appeared in the same record.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = how many entities were found and which is central.
`items` = shaped as
"name — role — connection to the identifier or another entity".

## Worked example
Facts: "הנכס רשום על שם דנה כהן"; "שעבוד לטובת בנק המזרחי"; "בקשת ההיתר
הוגשה על ידי ד. כהן".
`summary`: "שלושה גורמים סביב הנכס, כאשר דנה כהן היא הגורם המרכזי."
`items`: [
"דנה כהן — בעלת הנכס — רשומה כבעלים בחלק הבעלות",
"בנק המזרחי — מוטב שעבוד — לזכותו נרשם השעבוד על הנכס",
"ד. כהן — מבקש היתר — הגיש את בקשת ההיתר; ייתכן שזו דנה כהן אך השם מקוצר
ולא ניתן לאשר זהות"
]

## If no entities are named
Say so in `summary` and return an empty `items`. Never invent names or
roles.""",
    },
    {
        "content_key": "summary-evidence-quality",
        "kind": "skill",
        "name": "איכות הראיות",
        "description": "מעריך על מה הסיכום נשען וכמה אפשר לסמוך עליו.",
        "user_selectable": True,
        "content": """# Evidence quality

## What you produce
An assessment of the foundation the summary rests on: what is well covered
and what is fragile.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep section names exactly as supplied.

## Method
1. Go through the sections and mark each: succeeded, partial, or failed.
2. For each major conclusion, check how many sections support it.
3. Flag conclusions resting on a single section — those are the most
   fragile.
4. Flag sections that failed or returned zero rows, and say what they would
   have contributed.

## What weakens evidence — look for exactly these
- **Single source**: no cross-verification.
- **Partial coverage**: the package succeeded but returned less than
  expected, or with empty fields.
- **Failed package**: an entire domain is missing from the picture.
- **Staleness**: the fact is current as of an early date with no later
  update.

## Evidence rules
- Do not re-evaluate the facts themselves; evaluate their foundation.
- Never turn a methodological weakness into a claim that the fact is wrong.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = how well founded the summary is overall, and the main weakness.
`items` = shaped as
"what rests on what — type of weakness — what would strengthen it".

## Worked example
Facts: section "בעלות" succeeded; section "שעבודים" failed; section
"היתרים" partial.
`summary`: "הבעלות מבוססת היטב, אך תמונת החסמים חסרה: השעבודים לא נאספו
כלל וההיתרים חלקיים."
`items`: [
"מסקנת הבעלות נשענת על חלק הבעלות בלבד — מקור בודד — אימות מול מקור רישום
נוסף יחזק",
"תחום השעבודים חסר לגמרי — חבילה שנכשלה — הרצה חוזרת של חלק השעבודים
תשלים את תמונת החסמים",
"חלק ההיתרים החזיר נתונים חלקיים — כיסוי חלקי — יש לבדוק אם קיימות בקשות
נוספות שלא נאספו"
]

## If coverage is complete
Say so in `summary`, and use `items` to note which conclusions rest on a
single source.""",
    },
    {
        "content_key": "final-summary",
        "kind": "prompt",
        "name": "סיכום מלא",
        "description": "הנחיית ברירת מחדל לחיבור כל חלקי הסיכום.",
        "content": """Merge the supplied summary sections into one answer
about the identifier.

**Language:** the sections are in Hebrew and every string you return must
be in Hebrew. Keep names and identifiers exactly as written.

Return JSON with `summary`, `key_findings`, `risks`, `missing_data`, and
`suggested_questions`.

- Use only the supplied facts and evidence. Never guess and never add
  information from outside the sections.
- `summary` explains the overall picture; open with what matters most, not
  with a description of the process.
- `key_findings` holds the decisive facts, deduplicated across sections.
- `risks` holds only concerns the facts support. A gap is not a risk.
- `missing_data` names what was not covered, including failed sections.
- `suggested_questions` proposes follow-ups the existing evidence cannot
  already answer.
- State partial coverage openly. A failed section never invalidates the
  sections that succeeded.""",
    },
    {
        "content_key": "follow-up-router",
        "kind": "prompt",
        "name": "ניתוב שאלת המשך",
        "description": "בוחר תהליך detail שפורסם או משתמש בראיות קיימות.",
        "content": """Route a follow-up question.

Choose a single `workflow_key` ONLY if the existing evidence cannot answer
the question. If several workflows fit equally, return a `clarification`
instead of guessing. Never invent a tool or a workflow — use only the keys
supplied.

Any `clarification` text you return is shown to the user and must be
written in Hebrew.""",
    },
    {
        "content_key": "tool-aware-router",
        "kind": "prompt",
        "name": "ניתוב העמקה עם טולים",
        "description": "בוחר ראיות קיימות, workflow או טול עצמאי מאושר.",
        "content": """Choose exactly ONE action for the follow-up question:

- `use_cached` — the existing evidence already answers it.
- `workflow` — a published workflow is needed.
- `tool` — one approved standalone tool is enough.
- `clarify` — information is missing to decide.

Prefer `workflow` when several steps are required, and `tool` when a single
lookup suffices. Use only the keys and identifiers supplied; never invent
one.

Any `clarification` text you return is shown to the user and must be
written in Hebrew.""",
    },
    {
        "content_key": "workflow-planner",
        "kind": "prompt",
        "name": "מתכנן תהליכים מטולים",
        "description": "מרכיב טיוטת workflow או מסביר איזה טול חסר.",
        "content": """You plan a workflow draft for an FDE.

Use only a `package_version_id` that exists in the supplied catalog. Chain
steps according to the output fields shown in the examples, keep every
identifier a string, and return a DRAFT only — never publish.

If the request cannot be fulfilled, do not invent a tool. Add to
`missing_tools` a precise description of the required input, the expected
output, and why the existing catalog cannot cover it.

**Language:** the FDE reads Hebrew. Write `name`, `description`,
`rationale`, `system_prompt`, step names, and every `missing_tools`
description in Hebrew. Keep `package_version_id`, step keys, and field
names exactly as they appear in the catalog — never translate them.""",
    },
]
