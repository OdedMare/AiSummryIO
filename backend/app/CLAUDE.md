# Application root (`app/`)

`main.py` is the only implementation file at this level. It is the FastAPI
composition root: constructs dependencies once, registers middleware and
exception handlers, and maps HTTP routes to application services.

```text
Settings
  → RuntimeSettingsStore
  → Repository / OpenAIJsonClient / FlapiProvider
  → SummaryService
  → JobRunner
```

## Packages

| Package | Responsibility |
|---|---|
| [`api/`](api/CLAUDE.md) | Pydantic HTTP contracts and authentication |
| [`bl/`](bl/CLAUDE.md) | Workflow decisions, routing, synthesis, jobs |
| [`common/`](common/CLAUDE.md) | Dependency-light configuration and helpers |
| [`dal/`](dal/CLAUDE.md) | PostgreSQL, repository, LLM, and FLAPI I/O |

## `main.py`

- Starts the repository schema and recovers queued jobs.
- Converts `AppError` to its declared HTTP status and Hebrew message.
- Logs method, path, and status only—never bodies or credentials.
- Guards admin routes with the configured API token.
- Gives anonymous users a stable signed conversation session.

Route handlers stay short: validate through `api/models.py`, call one service
or repository operation, and return its result.

## Rules

- Do not add another implementation file beside `main.py`.
- HTTP contracts and auth go in `api/`.
- Business logic goes in `bl/`.
- External I/O and SQL go in `dal/`.
- Shared dependency-light code goes in `common/`.
- Never log API keys, passwords, raw provider bodies, or full user IDs.
