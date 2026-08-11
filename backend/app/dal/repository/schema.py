"""Database definition used during repository initialization."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS summary_packages (
    id TEXT PRIMARY KEY,
    package_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    package_id TEXT NOT NULL,
    input_cube_name TEXT NOT NULL,
    input_cube_parameter TEXT NOT NULL,
    input_mode TEXT NOT NULL CHECK (input_mode IN ('single','many')),
    input_kind TEXT NOT NULL DEFAULT 'both'
        CHECK (input_kind IN ('id','geometry','both')),
    output_cube_name TEXT NOT NULL,
    query_name TEXT NOT NULL DEFAULT '',
    timeout_seconds INTEGER,
    example_input JSONB NOT NULL DEFAULT '[]',
    example_output JSONB NOT NULL DEFAULT '[]',
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    agent_instructions TEXT NOT NULL DEFAULT '',
    output_schema JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS agent_instructions TEXT NOT NULL DEFAULT '';
ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS output_schema JSONB NOT NULL DEFAULT '{}';
-- 'both' keeps every already-published tool accepting what it accepted
-- before this column existed. Narrowing one is an explicit FDE decision.
ALTER TABLE summary_packages
    ADD COLUMN IF NOT EXISTS input_kind TEXT NOT NULL DEFAULT 'both';

-- ---------------------------------------------------------------------------
-- Why this script commits after every independent block instead of once at
-- the end.
--
-- The whole script text is sent to Postgres as a single simple-query
-- message, and Postgres implicitly wraps multiple statements in one message
-- into a single transaction unless the text itself commits along the way.
-- Without these checkpoints, one guarded migration failing on a particular
-- database's data (a legacy CHECK violation, an unexpected pre-existing
-- shape) rolls back every other statement already run in this call —
-- including unrelated `ADD COLUMN IF NOT EXISTS` statements that had nothing
-- to do with the failure. That previously left `summary_workflows` (and
-- `agent_content`) permanently missing `agent_enabled`: the backfill block
-- sits later in the script than the old `summary_feedback` rating CHECK, so
-- every startup re-failed at the earlier block before ever reaching and
-- committing the later one, and the app kept serving with a table that had
-- never actually been migrated.
--
-- Each COMMIT below closes out everything proven safe so far, so a failure
-- in one guarded block only blocks that block (and whatever follows it) on
-- this run, instead of undoing already-successful, unrelated schema work.
-- ---------------------------------------------------------------------------

COMMIT;

CREATE TABLE IF NOT EXISTS summary_workflows (
    id TEXT PRIMARY KEY,
    workflow_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('baseline','detail','both')),
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    system_prompt TEXT NOT NULL DEFAULT '',
    output_schema JSONB NOT NULL DEFAULT '{}',
    examples JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;

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
    input_value TEXT NOT NULL DEFAULT '',
    summary_prompt TEXT NOT NULL DEFAULT '',
    UNIQUE(workflow_id, step_key)
);

ALTER TABLE workflow_steps
    ADD COLUMN IF NOT EXISTS input_value TEXT NOT NULL DEFAULT '';

COMMIT;

CREATE TABLE IF NOT EXISTS agent_content (
    id TEXT PRIMARY KEY,
    content_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('skill','prompt')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    user_selectable BOOLEAN NOT NULL DEFAULT FALSE,
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS user_selectable BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;

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

-- A conversation may now be scoped by a drawn area alone, so the identifier
-- is optional. Existing rows already hold a value and are unaffected.
ALTER TABLE conversations ALTER COLUMN root_id DROP NOT NULL;

-- What the user asked, so history reads as a thread of questions rather than
-- a list of raw identifiers. Empty on existing rows, which the UI falls back
-- to rendering as it did before.
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '';

COMMIT;

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

COMMIT;

CREATE TABLE IF NOT EXISTS summary_evidence (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES summary_runs(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    step_key TEXT NOT NULL,
    records JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;

CREATE TABLE IF NOT EXISTS summary_feedback (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES summary_runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Add the rating CHECK constraint out-of-band instead of inline on the
-- CREATE TABLE above.
--
-- `CREATE TABLE IF NOT EXISTS` only applies to a table that does not exist
-- yet: on a database where `summary_feedback` was already created (an
-- earlier deployment, or a row written directly), the whole statement is
-- skipped and an inline CHECK there would never retroactively apply. Doing
-- it here, guarded on `pg_constraint`, means startup can also bring an
-- existing table up to the current rule.
--
-- The constraint would fail outright on a table that already carries a
-- legacy rating outside {-1,1} (a wider scale used before this table's
-- current contract, or a hand-written row), which is exactly the startup
-- crash this guards against. Clamping first — positive keeps the "up" vote,
-- everything else becomes "down" — makes adding the constraint safe on any
-- pre-existing data instead of taking the app down on every restart.
-- ---------------------------------------------------------------------------

UPDATE summary_feedback SET rating = CASE WHEN rating > 0 THEN 1 ELSE -1 END
WHERE rating NOT IN (-1, 1);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'summary_feedback_rating_check'
    ) THEN
        ALTER TABLE summary_feedback
            ADD CONSTRAINT summary_feedback_rating_check CHECK (rating IN (-1,1));
    END IF;
END $$;

COMMIT;

-- ---------------------------------------------------------------------------
-- Collapse the former append-only version history to one row per key.
--
-- Tools, workflows, and Skills used to be immutable versions: an FDE edit
-- inserted a new row and the catalog showed `DISTINCT ON (key) ... version
-- DESC`. Editing a published workflow therefore produced a fresh draft that
-- hid the published row still serving traffic, which read as "publishing did
-- not work". They are now edited in place, so a key has exactly one row.
--
-- Each block is guarded on the column it removes, so it runs once on an old
-- database and is skipped from then on. `summary_evidence.workflow_id` has no
-- foreign key and is deliberately left pointing at whatever ran — evidence is
-- the audit trail of runs that really happened.
--
-- Each block also commits on its own: `summary_packages`, `summary_workflows`
-- and `agent_content` are collapsed independently of one another, so an
-- unexpected shape in one of them cannot roll back a collapse that already
-- succeeded for the other two.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'summary_packages' AND column_name = 'version'
    ) THEN
        -- Steps pin a tool row, so they are moved to the surviving one before
        -- the others go: `package_version_id` has no ON DELETE clause and
        -- would otherwise block the delete as a constraint violation.
        UPDATE workflow_steps AS s
        SET package_version_id = keep.id
        FROM summary_packages AS old
        JOIN LATERAL (
            SELECT p.id FROM summary_packages AS p
            WHERE p.package_key = old.package_key
            ORDER BY p.version DESC LIMIT 1
        ) AS keep ON TRUE
        WHERE s.package_version_id = old.id
          AND s.package_version_id <> keep.id;

        DELETE FROM summary_packages AS p
        WHERE p.id <> (
            SELECT q.id FROM summary_packages AS q
            WHERE q.package_key = p.package_key
            ORDER BY q.version DESC LIMIT 1
        );

        ALTER TABLE summary_packages DROP COLUMN version;
    END IF;
END $$;

COMMIT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'summary_workflows' AND column_name = 'version'
    ) THEN
        -- The published row wins over a newer draft: it is the one that was
        -- actually answering requests, so keeping the draft would silently
        -- retire a live route. Steps cascade with the rows that go.
        DELETE FROM summary_workflows AS w
        WHERE w.id <> (
            SELECT x.id FROM summary_workflows AS x
            WHERE x.workflow_key = w.workflow_key
            ORDER BY (x.status = 'published') DESC, x.version DESC LIMIT 1
        );

        ALTER TABLE summary_workflows DROP COLUMN version;
    END IF;
END $$;

COMMIT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_content' AND column_name = 'version'
    ) THEN
        DELETE FROM agent_content AS c
        WHERE c.id <> (
            SELECT x.id FROM agent_content AS x
            WHERE x.content_key = c.content_key
            ORDER BY (x.status = 'published') DESC, x.version DESC LIMIT 1
        );

        ALTER TABLE agent_content DROP COLUMN version;
    END IF;
END $$;

COMMIT;

-- ---------------------------------------------------------------------------
-- Replace draft/published/archived with the `agent_enabled` switch tools
-- already use.
--
-- Publishing was a one-way transition guarded by its own validation, which
-- meant a workflow could exist in a state nothing could reach and the studio
-- had to explain the difference. What it actually controlled is whether the
-- agent may select the row, which is exactly what `agent_enabled` says.
--
-- `agent_enabled = (status = 'published')` preserves today's live behaviour
-- exactly: a draft or archived row was not being selected and stays
-- unselected, rather than going live the moment this migration runs.
-- ---------------------------------------------------------------------------

ALTER TABLE summary_workflows
    ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- Committed before the backfills below run: the column existing is what
-- every read and write in the app depends on, so it must survive even if a
-- backfill block fails outright on this particular database.
COMMIT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'summary_workflows' AND column_name = 'status'
    ) THEN
        UPDATE summary_workflows SET agent_enabled = (status = 'published');
        ALTER TABLE summary_workflows DROP COLUMN status;
        ALTER TABLE summary_workflows DROP COLUMN IF EXISTS published_at;
    END IF;
END $$;

COMMIT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_content' AND column_name = 'status'
    ) THEN
        UPDATE agent_content SET agent_enabled = (status = 'published');
        ALTER TABLE agent_content DROP COLUMN status;
        ALTER TABLE agent_content DROP COLUMN IF EXISTS published_at;
    END IF;
END $$;

COMMIT;

-- The key is the identity now. Declared as indexes rather than table
-- constraints so one statement serves both a fresh database and a migrated
-- one; `UNIQUE(key, version)` went with the dropped column.
CREATE UNIQUE INDEX IF NOT EXISTS summary_packages_key_idx
    ON summary_packages(package_key);
CREATE UNIQUE INDEX IF NOT EXISTS summary_workflows_key_idx
    ON summary_workflows(workflow_key);
CREATE UNIQUE INDEX IF NOT EXISTS agent_content_key_idx
    ON agent_content(content_key);

CREATE INDEX IF NOT EXISTS conversations_session_idx
    ON conversations(session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS runs_conversation_idx
    ON summary_runs(conversation_id, created_at);
"""
