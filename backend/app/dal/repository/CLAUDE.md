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
| `workflows.py` | Workflows, steps, publishing |
| `content.py` | Skills and prompts |
| `conversations.py` | Conversations, retention, and thread history |
| `runs.py` | Runs, progress, and evidence |
| `feedback.py` | Feedback and review queue |
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

## Collapsing the old version history

`schema.py` carries a one-time migration, guarded on the `version` column so
it runs once on an old database and is skipped afterwards. Per key it keeps a
single row: for workflows and content the **published** row wins over a newer
draft — that draft was the edit that hid the live row — and for tools the
highest version wins, since tools have no status. Steps are repointed to the
surviving tool before the others are deleted, because
`workflow_steps.package_version_id` has no `ON DELETE` clause and would
otherwise block the delete. `UNIQUE(key, version)` goes with the dropped
column and is replaced by a unique index on the key alone.

## Rules

- All application SQL stays in this directory.
- Persistence only: business decisions belong in `bl/`.
- Add behavior to the module that owns its table; keep the façade thin.
- Tools, workflows, and content are one row per key and edited in place.
  `create_*` refuses a key that already exists; `update_*` never rewrites the
  key itself, since steps, routing, and `published_content` all resolve by it.
- Publishing validates mappings and mandatory examples before changing state,
  and `update_workflow` re-runs that same validation when the row is already
  published — an edit must not break a route the agent is currently selecting,
  and must not silently unpublish it either.
- Secrets, raw request bodies, and full identifiers are never logged.
