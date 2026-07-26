# AiSummryIO backend context

Read this before changing `backend/`.

## Purpose

The backend turns one opaque string identifier into a traceable Hebrew
summary. An initial request runs all published `baseline`/`both` workflows.
Follow-ups reuse conversation evidence and run one relevant
`detail`/`both` workflow when needed.

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
- `dal/database.py` — PostgreSQL connection and schema creation.
- `dal/llm/` — LocatoAI's OpenAI-compatible JSON client and degradation
  ladder. Keep model/base URL/API key live per call.
- `dal/providers/flapi/` — FLAPI Flow Package adapter through `flunks`.
  Identifiers are opaque strings and enter `PackageInputCube.values`; never
  coerce them to integers. Package output is generic structured data;
  geometry is optional and rows must never be dropped for lacking it.
- `repository.py` — the only SQL owner.
- `workflow_engine.py` — dependency-aware execution, one retry, partial
  success, evidence retention, section summaries, and final synthesis.
- `jobs.py` — bounded background queue. Interactive follow-ups have priority.
- `main.py` — FastAPI routes and composition root.

## Locked rules

- The agent may select and parameterize only published, version-pinned
  workflows. It never invents package calls, HTTP, SQL, or mappings.
- A workflow input may reference `workflow.id` or an earlier step output.
- Package input mode is `single` or `many`; both preserve strings.
- Claims require evidence references. Package failures stay visible and do
  not discard successful sections.
- Never log API keys, admin passwords, raw package bodies, or full user IDs.
- Admin authentication uses a secure hash and an HttpOnly signed cookie.
- FDE edits create drafts. Publishing is blocked by invalid mappings or
  failing mandatory examples.
- Keep the design simple: add a module only when it owns a distinct boundary.

