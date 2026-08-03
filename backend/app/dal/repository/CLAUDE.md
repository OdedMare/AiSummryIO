# PostgreSQL repository (`app/dal/repository/`)

The only persistence owner in the application.

`Repository` is a 36-line public façade assembled from focused persistence
modules. It opens a connection per operation through
`dal/database/postgres.py`, so live settings apply without a restart.

| File | Responsibility |
|---|---|
| `repository.py` | Public façade and initialization only |
| `base.py` | Shared connection/query primitives and IDs |
| `packages.py` | Versioned FLAPI package catalog |
| `workflows.py` | Workflows, steps, publishing |
| `content.py` | Versioned Skills and prompts |
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

## Rules

- All application SQL stays in this directory.
- Persistence only: business decisions belong in `bl/`.
- Add behavior to the module that owns its table; keep the façade thin.
- Package, workflow, and content versions are append-only.
- Publishing validates mappings and mandatory examples before changing state.
- Secrets, raw request bodies, and full identifiers are never logged.
