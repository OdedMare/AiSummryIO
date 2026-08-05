"""Database definition used during repository initialization."""

SCHEMA = """
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(package_key, version)
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
    input_value TEXT NOT NULL DEFAULT '',
    summary_prompt TEXT NOT NULL DEFAULT '',
    UNIQUE(workflow_id, step_key)
);

ALTER TABLE workflow_steps
    ADD COLUMN IF NOT EXISTS input_value TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS agent_content (
    id TEXT PRIMARY KEY,
    content_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('skill','prompt','agent')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    user_selectable BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL CHECK (status IN ('draft','published','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE(content_key, version)
);

ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS user_selectable BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE agent_content
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}';
ALTER TABLE agent_content DROP CONSTRAINT IF EXISTS agent_content_kind_check;
ALTER TABLE agent_content ADD CONSTRAINT agent_content_kind_check
    CHECK (kind IN ('skill','prompt','agent'));

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
CREATE INDEX IF NOT EXISTS evidence_run_idx
    ON summary_evidence(run_id, created_at);
CREATE INDEX IF NOT EXISTS feedback_run_idx
    ON summary_feedback(run_id, created_at);
"""
