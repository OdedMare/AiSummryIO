# Backend documentation index

Start at [CLAUDE.md](CLAUDE.md) for product and runtime rules.

## Structure

```text
backend/app/
├── main.py                         FastAPI composition root and routes
├── api/
│   ├── auth.py                     cookies and signed authentication
│   └── models.py                   Pydantic HTTP contracts
├── bl/
│   ├── jobs.py                     background execution
│   ├── workflow_engine.py          stable SummaryService facade
│   └── workflow_engine_pkg/        execution, routing, planning, synthesis
├── common/
│   ├── config/                     environment defaults
│   └── runtime_settings/           live configuration
└── dal/
    ├── database/                   PostgreSQL connection setup
    ├── llm/                        OpenAI-compatible client
    ├── providers/flapi/            FLAPI/flunks adapter
    └── repository/                 focused persistence modules and all SQL
```

Every implementation concern lives in a package. `main.py` is deliberately
the only implementation file at the root of `app/`.

## Directory docs

| Area | Documentation |
|---|---|
| Composition root | [app/CLAUDE.md](app/CLAUDE.md) |
| HTTP models and auth | [app/api/CLAUDE.md](app/api/CLAUDE.md) |
| Business logic | [app/bl/CLAUDE.md](app/bl/CLAUDE.md) |
| Shared utilities | [app/common/CLAUDE.md](app/common/CLAUDE.md) |
| Data access | [app/dal/CLAUDE.md](app/dal/CLAUDE.md) |
| Repository | [app/dal/repository/CLAUDE.md](app/dal/repository/CLAUDE.md) |
| LLM client | [app/dal/llm/CLAUDE.md](app/dal/llm/CLAUDE.md) |
| FLAPI adapter | [app/dal/providers/flapi/CLAUDE.md](app/dal/providers/flapi/CLAUDE.md) |
| Tests | [tests/CLAUDE.md](tests/CLAUDE.md) |

## Request path

```text
POST /api/summaries                     app/main.py
  ├── Repository.create_run             dal/repository/
  └── JobRunner.submit                  bl/jobs.py
        └── SummaryService              bl/workflow_engine.py
              ├── execution             bl/workflow_engine_pkg/execution.py
              ├── FlapiProvider         dal/providers/flapi/
              ├── Repository evidence   dal/repository/
              └── synthesis             bl/workflow_engine_pkg/synthesis.py
```

## Non-negotiable rules

- Python 3.8.10-compatible annotations.
- Identifiers are opaque strings; never coerce them to integers.
- SQL lives only in `app/dal/repository/`.
- Business decisions live in `app/bl/`.
- Package failures remain visible and never discard successful sections.
- User-facing errors are Hebrew and tests assert on their wording.
