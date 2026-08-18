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
-- database's data (an unexpected legacy CHECK violation, a shape none of the
-- guards anticipated) rolls back every other statement already run in this
-- call — including unrelated `ADD COLUMN IF NOT EXISTS` statements that had
-- nothing to do with the failure. That is exactly what once left
-- `summary_workflows` (and `agent_content`) permanently missing
-- `agent_enabled`: the backfill block sits later in this file than the
-- `summary_feedback` rating CHECK, so a startup that failed on that legacy
-- data re-failed at the same earlier block on every restart, before ever
-- reaching and committing the later one — and the app kept serving with a
-- table that had never actually been migrated.
--
-- Each COMMIT below closes out everything proven safe so far, so a failure
-- in one guarded block only blocks that block (and whatever follows it) on
-- this run, instead of undoing already-successful, unrelated schema work.
-- Add a new guarded migration after its own COMMIT so the same isolation
-- holds for it too.
-- ---------------------------------------------------------------------------

COMMIT;

CREATE TABLE IF NOT EXISTS summary_workflows (
    id TEXT PRIMARY KEY,
    workflow_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('baseline','detail','both')),
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    agent_id TEXT,
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
    kind TEXT NOT NULL CHECK (kind IN ('skill','prompt','agent')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    user_selectable BOOLEAN NOT NULL DEFAULT FALSE,
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS user_selectable BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}';
ALTER TABLE agent_content DROP CONSTRAINT IF EXISTS agent_content_kind_check;
ALTER TABLE agent_content ADD CONSTRAINT agent_content_kind_check
    CHECK (kind IN ('skill','prompt','agent'));

-- A workflow has one real owner in the relational schema. Specialist configs
-- used to carry workflow keys inside JSON, which made saving a workflow unable
-- to assign it atomically and allowed the two records to drift apart. The
-- foreign key is added after `agent_content` exists below, and the legacy JSON
-- assignments are backfilled after the old version rows have been collapsed.
ALTER TABLE summary_workflows
    ADD COLUMN IF NOT EXISTS agent_id TEXT;

COMMIT;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mission TEXT NOT NULL,
    tool_keys JSONB NOT NULL DEFAULT '[]',
    workflow_keys JSONB NOT NULL DEFAULT '[]',
    skill_keys JSONB NOT NULL DEFAULT '[]',
    agent_keys JSONB NOT NULL DEFAULT '[]',
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Existing installations already have the table. The default leaves every
-- user-created project untouched; the repository lazily creates the one
-- system workspace after the catalog seeds have finished loading.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;

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

-- Nullable keeps every legacy row valid. When the session first loads its
-- projects, those rows are attached to its Hunger Games system workspace.
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id)
        ON DELETE SET NULL;

COMMIT;

CREATE TABLE IF NOT EXISTS summary_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('full','follow_up')),
    question TEXT NOT NULL DEFAULT '',
    skill_keys JSONB NOT NULL DEFAULT '[]',
    agent_keys JSONB NOT NULL DEFAULT '[]',
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

ALTER TABLE summary_runs
    ADD COLUMN IF NOT EXISTS agent_keys JSONB NOT NULL DEFAULT '[]';

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
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;

CREATE TABLE IF NOT EXISTS evaluation_batches (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    label TEXT NOT NULL,
    question TEXT NOT NULL,
    skill_keys JSONB NOT NULL DEFAULT '[]',
    agent_keys JSONB NOT NULL DEFAULT '[]',
    cooldown_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (cooldown_seconds BETWEEN 0 AND 3600),
    status TEXT NOT NULL CHECK (
        status IN (
            'running','pausing','paused','stopping','stopped','completed'
        )
    ),
    next_start_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

ALTER TABLE evaluation_batches
    ADD COLUMN IF NOT EXISTS agent_keys JSONB NOT NULL DEFAULT '[]';
ALTER TABLE evaluation_batches
    ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id)
        ON DELETE SET NULL;

COMMIT;

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    root_id TEXT NOT NULL,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES summary_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','failed','stopped')),
    error TEXT NOT NULL DEFAULT '',
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(batch_id, position)
);

COMMIT;

-- Feedback moved from thumbs up/down (-1/1) to a 1-5 star rating, so the
-- router (`bl/workflow_engine_pkg/routing.py`) has a graded quality signal
-- per route instead of a binary one. `DROP ... IF EXISTS` then re-`ADD` is
-- idempotent on the constraint's own *definition*, but `ADD CONSTRAINT`
-- also validates every row already in the table — and a database that was
-- live under the old scale still has -1 rows sitting in it. Re-adding the
-- constraint against those crashed startup outright, every restart, with
-- no way for the app to ever come up and let anyone fix the data by hand.
DO $$
DECLARE
    previous_def TEXT;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO previous_def
    FROM pg_constraint
    WHERE conrelid = 'summary_feedback'::regclass
      AND conname = 'summary_feedback_rating_check';

    -- Drop it up front (if present) so the translation below — and the
    -- generic clamp after it — can write values the constraint being
    -- replaced would not itself have allowed, e.g. 5 while the old -1/1
    -- check is still live.
    ALTER TABLE summary_feedback DROP CONSTRAINT IF EXISTS summary_feedback_rating_check;

    -- Positive evidence this was still the old thumbs up/down check — a
    -- literal -1 is the one thing that appears in that definition and
    -- never in `BETWEEN 1 AND 5`. Only then translate old rows onto the
    -- new scale's meaning (down -> worst star, up -> best star), and only
    -- once: after this first successful run the constraint reads
    -- `BETWEEN 1 AND 5`, so a genuine 1-star rating collected afterward is
    -- never mistaken for the old thumbs-up again. A bare clamp instead of
    -- this translation would have turned every past thumbs-up into the new
    -- scale's *worst* rating, wrongly filling `review_queue()`'s
    -- `rating <= 2` list with what were actually positive runs.
    IF previous_def LIKE '%-1%' THEN
        UPDATE summary_feedback SET rating = CASE
            WHEN rating = -1 THEN 1
            WHEN rating = 1 THEN 5
            ELSE rating
        END;
    END IF;
END $$;

-- Belt-and-braces regardless of the constraint's prior shape: no rating
-- this app writes today is outside 1-5, so clamping anything still out of
-- range is always safe and is what actually guarantees the ADD CONSTRAINT
-- below cannot fail on this table again.
UPDATE summary_feedback SET rating = LEAST(GREATEST(rating, 1), 5)
WHERE rating NOT BETWEEN 1 AND 5;

ALTER TABLE summary_feedback ADD CONSTRAINT summary_feedback_rating_check
    CHECK (rating BETWEEN 1 AND 5);

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
        WHERE table_schema = current_schema()
          AND table_name = 'summary_packages' AND column_name = 'version'
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
        WHERE table_schema = current_schema()
          AND table_name = 'summary_workflows' AND column_name = 'version'
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
        WHERE table_schema = current_schema()
          AND table_name = 'agent_content' AND column_name = 'version'
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
        WHERE table_schema = current_schema()
          AND table_name = 'summary_workflows' AND column_name = 'status'
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
        WHERE table_schema = current_schema()
          AND table_name = 'agent_content' AND column_name = 'status'
    ) THEN
        UPDATE agent_content SET agent_enabled = (status = 'published');
        ALTER TABLE agent_content DROP COLUMN status;
        ALTER TABLE agent_content DROP COLUMN IF EXISTS published_at;
    END IF;
END $$;

COMMIT;

-- Move the old JSON ownership into the workflow row, preferring an enabled
-- specialist if legacy data somehow named the same workflow more than once.
-- Once backfilled, remove the duplicate JSON field: API responses reconstruct
-- `config.workflow_keys` from this column for backward compatibility.
UPDATE summary_workflows AS workflow
SET agent_id = (
    SELECT content.id
    FROM agent_content AS content
    WHERE content.kind = 'agent'
      AND jsonb_typeof(content.config) = 'object'
      AND COALESCE(content.config->'workflow_keys', '[]'::jsonb)
          ? workflow.workflow_key
    ORDER BY content.agent_enabled DESC, content.created_at, content.id
    LIMIT 1
)
WHERE workflow.agent_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM agent_content AS content
      WHERE content.kind = 'agent'
        AND jsonb_typeof(content.config) = 'object'
        AND COALESCE(content.config->'workflow_keys', '[]'::jsonb)
            ? workflow.workflow_key
  );

UPDATE agent_content
SET config = config - 'workflow_keys'
WHERE kind = 'agent' AND jsonb_typeof(config) = 'object'
  AND config ? 'workflow_keys';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'summary_workflows'::regclass
          AND conname = 'summary_workflows_agent_id_fkey'
    ) THEN
        ALTER TABLE summary_workflows
            ADD CONSTRAINT summary_workflows_agent_id_fkey
            FOREIGN KEY (agent_id) REFERENCES agent_content(id)
            ON DELETE SET NULL;
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
CREATE INDEX IF NOT EXISTS summary_workflows_agent_idx
    ON summary_workflows(agent_id);
CREATE INDEX IF NOT EXISTS projects_session_idx
    ON projects(session_id, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS projects_one_system_idx
    ON projects(session_id) WHERE is_system IS TRUE;

CREATE INDEX IF NOT EXISTS conversations_session_idx
    ON conversations(session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS runs_conversation_idx
    ON summary_runs(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS evidence_run_idx
    ON summary_evidence(run_id, created_at);
CREATE INDEX IF NOT EXISTS feedback_run_idx
    ON summary_feedback(run_id, created_at);
CREATE INDEX IF NOT EXISTS evaluation_cases_batch_idx
    ON evaluation_cases(batch_id, position);
CREATE UNIQUE INDEX IF NOT EXISTS evaluation_one_active_idx
    ON evaluation_batches ((TRUE))
    WHERE status IN ('running','pausing','paused','stopping');
"""
