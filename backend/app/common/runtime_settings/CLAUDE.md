# Runtime settings (`app/common/runtime_settings/`)

The **live** configuration the whole app reads. Settings saved in the admin UI
override env defaults and take effect immediately, without a restart, because
`bl/` and `dal/` call `store.get()` on every operation instead of caching.

| File | Lines | Role |
|---|---|---|
| `runtime_settings.py` | 27 | `RuntimeSettings` — a plain dataclass of the live values |
| `runtime_settings_store.py` | 131 | `RuntimeSettingsStore` — load, override, mask, persist |
| `normalizers.py` | 90 | Cleaning and validating URLs and schema names |

## How a value is resolved

1. `Settings` (env + `.env`) supplies defaults — see
   [config/CLAUDE.md](../config/CLAUDE.md).
2. The constructor copies them into `RuntimeSettings`, running env values
   through the **same normalizers** as UI edits, so a `jdbc:` URL works
   however it arrives. `database_schema` needs `Settings.model_fields_set` for
   this, not a truthiness check: the field carries a non-empty class default,
   so an env value and an unset field are otherwise indistinguishable, and a
   plain `env.database_schema or extract_url_schema(...)` would always take
   the default and never see a JDBC `?currentSchema=`. An env var (or
   `.env` entry) that actually sets `database_schema` still wins over the
   URL, matching the explicit-field-wins rule `_apply` uses for a live patch.
3. If `runtime-settings.json` exists, it is applied on top (non-strict: bad
   values are skipped rather than blocking startup).
4. Startup fills one gap and persists if it fired: a random `cookie_secret`
   when unset.

## The store's API

- `get()` — the live `RuntimeSettings`. Call this per operation, never cache.
- `public()` — for the API. Every field in `_SECRET_FIELDS` becomes `********`
  (or `""` if unset). Secrets never leave the backend.
- `update(patch)` — applies a patch **strictly** (invalid values raise), then
  writes `runtime-settings.json`.

`_apply` has three rules worth knowing:

- **`"********"` is ignored.** The UI sends back the masked value for
  untouched secrets; treating it as real would overwrite the token with
  asterisks.
- **`_NULLABLE` fields** (`database_port`, `llm_base_url`, `flapi_username`)
  treat empty as "clear this", not "keep current" — otherwise a cleared base
  URL could never be unset from the UI.
- `None` for any other field means "keep current".

Integer limits are floored at 1.

## `normalizers.py`

Users paste connection strings from other tools, so input is cleaned rather
than rejected:

- `normalize_database_url` — strips a `jdbc:` prefix, requires
  `postgresql://` / `postgres://`, and translates the schema (below).
- `_translate_current_schema` — rewrites JDBC's `currentSchema=x` into libpq's
  `options=-csearch_path%3Dx`. **libpq rejects the unknown keyword outright**,
  so a working JDBC string would otherwise fail to connect at all. Also repairs
  the `?&` left behind when the first query parameter is removed.
- `extract_url_schema` — lets a pasted JDBC URL set `database_schema` without
  the user also filling the separate field. An explicit field in the same patch
  wins.
- `normalize_database_schema` — must match `^[A-Za-z_][A-Za-z0-9_]*$`. **This
  value is interpolated into `SET search_path`**, so it can never accept
  arbitrary strings. Same rule LocatoAI uses for `layers_table`.
- `normalize_llm_base_url` — strips `/chat/completions`, `/completions`, and
  `/models` suffixes, because the OpenAI SDK appends the path itself and would
  otherwise 404.

## Rules

- Never log or return a secret. Add new credentials to `_SECRET_FIELDS`.
- Startup must not crash on a bad env value — `_safe_database_url` and
  `_safe_schema` fall back so the failure surfaces later as a real connection
  error naming the URL, which is far clearer than a crash during settings
  construction.
- UI edits are strict; env and file values are lenient.
