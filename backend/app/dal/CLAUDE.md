# Data access layer (`app/dal/`)

Everything that talks to something outside this process: PostgreSQL, the LLM
endpoint, and FLAPI. No business rules live here — the DAL fetches, sends, and
translates; `bl/` decides.

## Subdirectories

| Path | Owns | Docs |
|---|---|---|
| `database/` | PostgreSQL connections and schema creation | below |
| `llm/` | OpenAI-compatible JSON client + degradation ladder | [llm/CLAUDE.md](llm/CLAUDE.md) |
| `providers/flapi/` | FLAPI Flow Packages through `flunks` | [providers/flapi/CLAUDE.md](providers/flapi/CLAUDE.md) |

`repository.py` — the only SQL owner — sits one level up at
[app/repository.py](../repository.py), not here, and is described in
[app/CLAUDE.md](../CLAUDE.md).

## `database/postgres.py`

Two functions, both driven by live runtime settings (never a cached config):

- `connect(store)` — opens a `psycopg` connection with `dict_row`, then issues
  `SET search_path TO <schema>, public` when a schema is configured. Every
  unqualified table name in `repository.py` resolves through `search_path`, so
  this one statement places all DDL and queries in the right schema without
  touching a single query.
- `ensure_schema(store)` — `CREATE SCHEMA IF NOT EXISTS`. The app creates its
  own tables, so it must be able to create the schema holding them; otherwise
  the first `CREATE TABLE` fails on a fresh database. Called at startup.

`_credentials(settings)` builds the connection kwargs: explicit
`database_user` / `password` / `host` / `port` / `name` fields **override**
whatever the URL carries. Empty means "not set" and is omitted entirely rather
than passed as `""`.

Schema names are interpolated into SQL, so they are validated as plain
identifiers by `normalize_database_schema` in
[common/runtime_settings/normalizers.py](../common/runtime_settings/normalizers.py)
and wrapped in `sql.Identifier` here. Never bypass both.

## Rules

- Live settings on every call. A user saving settings in the UI must take
  effect without a restart, so nothing here caches a connection string.
- Errors leaving the DAL are `app.common.errors` types in Hebrew, not raw
  driver exceptions.
- Never log credentials, API keys, or full user identifiers.
