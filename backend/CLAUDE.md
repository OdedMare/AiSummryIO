# AiSummryIO backend context

Read this before changing `backend/`.

## Purpose

The backend turns one opaque string identifier into a traceable Hebrew
summary. An initial request runs all published `baseline`/`both` workflows.
Follow-ups reuse conversation evidence and run one relevant
`detail`/`both` workflow or one FDE-approved standalone tool when needed.

## Runtime and commands

Python is exactly **3.8.10**, matching LocatoAI. Keep annotations compatible:
use `Optional`, `List`, and `Dict`; do not use `X | Y`, `list[str]`, or
`match`.

```bash
cd backend
python -m pytest -q
uvicorn app.main:app --reload
```

## Architecture

- `common/` — env defaults plus the live `runtime-settings.json` override
  store. Saved settings override env without restart; secrets are masked.
- `dal/database/postgres.py` — PostgreSQL connection and schema creation.
- `dal/llm/` — LocatoAI's OpenAI-compatible JSON client and degradation
  ladder. Keep model/base URL/API key live per call.
- `dal/providers/flapi/` — FLAPI Flow Package adapter through `flunks`.
  Identifiers are opaque strings and enter `PackageInputCube.values`; never
  coerce them to integers. Package output is generic structured data;
  geometry is optional and rows must never be dropped for lacking it.
  - `provider.py` — run one package, normalize, retry once. Nothing else.
  - `mapper.py` — translate package definitions to/from `flunks` models.
  - `runner_config.py` — timeout policy and `FlApiConfig` construction. The
    class is `FlApiConfig` (capital A), matching LocatoAI; `verify_tls` is
    passed only when the installed `flunks` exposes such a field.
- `repository.py` — the only SQL owner.
- `bl/workflow_engine.py` — `SummaryService`: execution, one retry, partial
  success, evidence retention, section summaries, and final synthesis. A
  workflow's `output_schema` extends the shared section contract; extras are
  returned under `section.fields`. It also owns standalone tool routing and FDE
  workflow planning.
- `bl/jobs.py` — `JobRunner`: bounded background queue. Interactive follow-ups
  have priority.
- `main.py` — FastAPI routes and composition root.

Business logic lives under `bl/` and data access under `dal/`, mirroring
LocatoAI. A file owns one class or one concern; split rather than append.

## Locked rules

- The agent may select only published, version-pinned workflows or the latest
  FDE-approved standalone tool version. It never invents package calls, HTTP,
  SQL, or mappings.
- Workflow planning creates a draft from catalog tool-version IDs or describes
  a missing tool contract; it never publishes automatically.
- A workflow input may reference `workflow.id` or an earlier step output.
- Package input mode is `single` or `many`; both preserve strings.
- Claims require evidence references. Package failures stay visible and do
  not discard successful sections.
- Never log API keys, admin passwords, raw package bodies, or full user IDs.
- Admin authentication uses a secure hash and an HttpOnly signed cookie.
- FDE edits create drafts. Publishing is blocked by invalid mappings or
  failing mandatory examples.
- Keep the design simple: add a module only when it owns a distinct boundary.
