# PostgreSQL repository (`app/dal/repository/`)

The only persistence owner in the application.

`Repository` is a 36-line public façade assembled from focused persistence
modules. It opens a connection per operation through
`dal/database/postgres.py`, so live settings apply without a restart.

| File | Responsibility |
|---|---|
| `repository.py` | Public façade and initialization only |
| `base.py` | Shared connection/query primitives and IDs |
| `packages.py` | FLAPI package (tool) catalog |
| `projects.py` | Session-owned mission workspaces and catalog assignments |
| `workflows.py` | Workflows and their steps |
| `content.py` | Skills and prompts |
| `conversations.py` | Conversations, retention, and thread history |
| `runs.py` | Runs, progress, and evidence |
| `feedback.py` | Feedback, the review queue, and per-route rating aggregates |
| `validation.py` | Pure workflow-step validation |
| `schema.py` | DDL used at startup |
| `seed_content.py` | Built-in Skills and prompts |

## Conversation history

`conversation_history` projects `summary_runs` into question/answer turns.
**There is no messages table, deliberately.** A run already holds the user's
`question` and the assistant's `result`, so a second table would be a parallel
source of truth that drifts whenever a run fails, retries, or is recovered by
`queued_runs()` at startup.

Only `completed`/`partial` runs are returned: a queued or failed run has no
answer, and offering it as context would invite the model to treat a question
that was never answered as if it had been. The newest turns are selected and
then reversed, so a long thread keeps its most recent context.

## Citations

`summary_runs.citation_context` stores the citation a follow-up was asked
about. It lives on the run for the same reason `skill_keys` does: the job
worker re-reads the row, not the HTTP body. It defaults to `'{}'`, so every
run written before citations existed reads back fine.

The citation → evidence → record mapping itself is **not** a new table. A
citation is derived from `summary_evidence` rows that a run already saved and
published inside that run's `result`, so there is one source of truth and
nothing to drift. `conversation_runs` reads a thread's finished runs to resolve
a citation across turns, and `evidence_record` is `evidence_page` bounded to
its first rows — scoped by `run_id` **and** `evidence_id`, so a caller who
passed the run's ownership check still cannot reach another run's evidence.

## Feedback ratings

`summary_feedback.rating` is a 1-5 star rating (`CHECK (rating BETWEEN 1 AND
5)`), rating a whole run's answer rather than one workflow in isolation.
`route_ratings()` turns that into an average per **route** — a real
workflow's row id, or `"tool:" + package_version_id"` for a standalone tool —
keyed exactly as `summary_evidence.workflow_id` already is, so the caller
never has to join back to `summary_workflows`/`summary_packages`. A run
answered by several workflows counts its rating toward each of them, which is
why `routing.py` treats a route's `rating_count` as a confidence signal, not
just its `avg_rating`. `review_queue()` still lists a run for an FDE to look
at on a poor rating (`rating <= 2`) or any left comment.

`schema.py` migrates the constraint itself, not just the column: it was
`CHECK (rating IN (-1,1))` (thumbs up/down) before the 1-5 scale. `ADD
CONSTRAINT` validates every existing row, so re-adding it unconditionally
against a database still carrying old -1 rows failed startup outright, on
every restart. The migration now drops the old constraint, and — only when
`pg_get_constraintdef` shows positive evidence it *was* the old one (a
literal `-1`, which never appears in `BETWEEN 1 AND 5`) — translates old
rows onto the new scale's meaning (thumbs-down to the worst star, thumbs-up
to the best) before re-adding it. That evidence check is what keeps this
one-time: once the constraint reads `BETWEEN 1 AND 5`, a genuine 1-star
rating collected afterward is never mistaken for the old thumbs-up again. A
final unconditional clamp is belt-and-braces for anything still out of
range regardless of the constraint's prior shape.

## Collapsing the old version history and publish state

`schema.py` carries a one-time migration, guarded on the `version` column so
it runs once on an old database and is skipped afterwards. Per key it keeps a
single row: for workflows and content the **published** row wins over a newer
draft — that draft was the edit that hid the live row — and for tools the
highest version wins, since tools have no status. Steps are repointed to the
surviving tool before the others are deleted, because
`workflow_steps.package_version_id` has no `ON DELETE` clause and would
otherwise block the delete. `UNIQUE(key, version)` goes with the dropped
column and is replaced by a unique index on the key alone.

A second guarded block replaces `status` with `agent_enabled`, set from
`status = 'published'` so a draft or archived row stays unselected instead of
going live the moment the migration runs.

`schema.py` is sent to Postgres as one script, and a `COMMIT;` sits after
every independent block. Without those, the whole script runs as a single
implicit transaction, so one guarded block failing on a particular database's
data rolls back every other statement already run in that call — including
unrelated `ADD COLUMN IF NOT EXISTS` statements. That once left
`summary_workflows` permanently missing `agent_enabled`: the backfill sits
later in the file than the `summary_feedback` rating migration above, so a
startup that failed there re-failed at the same earlier block on every
restart, before ever reaching and committing the later one. Add a new guarded
migration after its own `COMMIT;` so a failure there stays contained to it.

## Rules

- All application SQL stays in this directory.
- Persistence only: business decisions belong in `bl/`.
- Add behavior to the module that owns its table; keep the façade thin.
- Tools, workflows, and content are one row per key and edited in place.
  `create_*` refuses a key that already exists; `update_*` never rewrites the
  key itself, since steps, routing, and `enabled_content` all resolve by it.
- There is no publishing. `agent_enabled` is an ordinary column written by
  the same create/update as every other field, and `enabled_workflows`,
  `enabled_summary_skills`, and `enabled_content` are what the agent reads.
  `validate_steps` on create and update is the structural gate; owner selection
  is validated separately against real specialist rows.
- A workflow's specialist owner is `summary_workflows.agent_id`, a foreign key
  to the owning `agent_content` row. `config.workflow_keys` is an API projection
  built from that column, never stored. Saving from either editor updates the
  same owner field; enabling a workflow requires an owner once specialists
  exist.
- `delete_*` takes a row id. A tool is refused while a workflow step points at
  it, and the blocking workflows are named; a workflow and a Skill or prompt
  have nothing pinning them, so they go. Deleting content is a reset for a
  built-in — seeding recreates a missing key at the next startup, and
  `enabled_content` falls back to the prompt under `bl/prompts/` meanwhile —
  and permanent for anything an FDE created.
- Secrets, raw request bodies, and full identifiers are never logged.
- Projects own only their mission and exact catalog keys. They do not copy
  tools, Workflows, Skills, or agents, so editing a capability still has one
  source of truth. Every project read and write is scoped to `session_id`.
- `list_projects` lazily creates one `is_system` project named `Hunger Games`
  per session after catalog seeding, snapshots all existing capability keys,
  and attaches legacy conversations with a null `project_id`. A partial unique
  index makes that migration idempotent; the system project cannot be deleted.
