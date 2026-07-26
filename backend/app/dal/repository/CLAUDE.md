# PostgreSQL repository (`app/dal/repository/`)

The only persistence owner in the application.

`Repository` owns schema creation, versioned packages and workflows, agent
content, conversations, runs, evidence, and feedback. It opens a connection
per operation through `dal/database/postgres.py`, so live settings apply
without a restart.

## Rules

- All application SQL stays in this directory.
- Persistence only: business decisions belong in `bl/`.
- Package, workflow, and content versions are append-only.
- Publishing validates mappings and mandatory examples before changing state.
- Secrets, raw request bodies, and full identifiers are never logged.
