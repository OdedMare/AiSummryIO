# Application root (`app/`)

The composition root plus the three files that belong to no layer.

| File | Lines | Owns |
|---|---|---|
| `main.py` | 284 | FastAPI routes, middleware, dependency wiring |
| `repository.py` | 736 | **The only SQL owner** |
| `models.py` | 181 | Pydantic request/response models |
| `auth.py` | 58 | Signed admin tokens and session cookies |

Layer docs: [bl/](bl/CLAUDE.md) · [dal/](dal/CLAUDE.md) ·
[common/](common/CLAUDE.md)

## `main.py` — composition root

Everything is constructed once, at import, in dependency order
([main.py:28-34](main.py#L28-L34)):

```
env        = Settings()                    # env defaults
store      = RuntimeSettingsStore(env)     # live settings
repository = Repository(store)
llm        = OpenAIJsonClient(store)
provider   = FlapiProvider(store)
service    = SummaryService(repository, provider, llm, store)
jobs       = JobRunner(repository, service, max_parallel_workflows)
```

Every collaborator is injected, which is why the service and provider are
testable without a database, a model, or a flunks wheel. On startup the app
calls `repository.initialize()` (schema + tables) and `jobs.recover()`
(re-queues runs orphaned by a restart).

**Exception handlers** turn `AppError` into its own `status_code` and a
`{"detail": ...}` body — this is why each error class in
[common/errors.py](common/errors.py) carries a status. Bare `ValueError`
becomes 422.

**Request logging** middleware records method, path, and status only — never
bodies, identifiers, or credentials — to the logger and to
`env.request_log_path` as JSONL. Log-file failures are swallowed: logging must
never break a request.

**Two auth dependencies**: `admin_dependency` guards every FDE/admin route via
the `aisummry_admin` cookie; `user_session` reads `aisummry_session` and mints
a fresh UUID when it is missing or invalid, so anonymous users still get a
stable conversation history.

Route groups: public summary/conversation endpoints, and
`/api/admin/*`, `/api/settings`, `/api/packages`, `/api/workflows`,
`/api/models` behind `admin_dependency`.

## `repository.py` — the only SQL owner

No SQL exists anywhere else in the backend. It opens a connection per
operation through `dal/database/postgres.connect`, so live settings changes
apply immediately.

**Versioning model.** Packages, workflows, and agent content are
append-only: `create_*` computes `_next_version(...)` and inserts a new row
rather than updating. `list_*` uses `DISTINCT ON (key) ... ORDER BY key,
version DESC` to return the latest of each. FDE edits therefore always create
drafts, and published versions are immutable.

**Validation happens here, before persistence:**

- `_validate_steps` — rejects a step referencing a *later* step
  (`input_source: steps.X` where X comes after), and rejects reading an
  earlier step's output without declaring it in `depends_on`.
- `_validate_for_publish` — blocks publishing on invalid mappings or failing
  mandatory examples.

`initialize()` calls `ensure_schema` first, because the schema must exist
before any `CREATE TABLE` can resolve into it, then executes `_SCHEMA`
([repository.py:485](repository.py#L485)) and seeds default agent content.

Tables: `summary_packages`, `summary_workflows`, `workflow_steps`,
`agent_content`, `conversations`, `summary_runs`, `summary_evidence`,
`summary_feedback`.

## `models.py`

Pydantic models for the API boundary. Notable:

- `PackageCreate` — the FLAPI package contract (`package_id`,
  `input_cube_name`, `input_cube_parameter`, `input_mode`,
  `output_cube_name`, `query_name`, `timeout_seconds`). Field meanings are in
  [dal/providers/flapi/CLAUDE.md](dal/providers/flapi/CLAUDE.md).
- `GeoBoundaries` — validates the drawn map area. Rings must be **closed**;
  only `MultiPolygon` is accepted. Conversion to WKT is
  [common/geometry.py](common/geometry.py).

## `auth.py`

HMAC-SHA256 over `store.get().cookie_secret`, so rotating the secret
invalidates every token.

- **Admin**: `admin_token` issues `timestamp.signature`;
  `require_admin_token` re-signs and compares with `hmac.compare_digest`,
  rejecting anything older than `_ADMIN_TTL_SECONDS` (12h) or
  negative-aged. `login` verifies the scrypt hash from the settings store.
- **Session**: `session_signature` / `verify_session` sign an opaque session
  ID. No expiry — the cookie carries a 30-day `max_age`.

Cookies are set `httponly=True, samesite="lax"`. Password hashing itself lives
in [common/runtime_settings/](common/runtime_settings/CLAUDE.md).

## Rules

- SQL stays in `repository.py`. Business logic stays in `bl/`. External I/O
  stays in `dal/`.
- A file owns one class or one concern; split rather than append.
- Never log API keys, admin passwords, raw package bodies, or full user IDs.
