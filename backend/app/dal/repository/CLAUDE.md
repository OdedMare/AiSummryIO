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
| `conversations.py` | Conversations and retention |
| `runs.py` | Runs, progress, and evidence |
| `feedback.py` | Feedback and review queue |
| `validation.py` | Pure workflow-step validation |
| `schema.py` | DDL used at startup |
| `seed_content.py` | Built-in Skills and prompts |

## Rules

- All application SQL stays in this directory.
- Persistence only: business decisions belong in `bl/`.
- Add behavior to the module that owns its table; keep the façade thin.
- Package, workflow, and content versions are append-only.
- Publishing validates mappings and mandatory examples before changing state.
- Secrets, raw request bodies, and full identifiers are never logged.
