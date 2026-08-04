# Environment defaults (`app/common/config/`)

One file: `settings.py`, holding the pydantic `Settings` class.

## What this is — and is not

`Settings` is **only the source of defaults**. It is read from the environment
(prefix `AISUMMRY_`, plus `.env`) exactly once, at startup, in
[main.py:28](../../main.py#L28), and immediately handed to
`RuntimeSettingsStore`.

**Nothing else in the app should read `Settings` directly.** Values the user
can edit in the UI live in
[common/runtime_settings/](../runtime_settings/CLAUDE.md), which overrides
these defaults from `runtime-settings.json` and is what `bl/` and `dal/`
actually consume. Reading `Settings` at call time would silently ignore
everything the user saved in the settings panel.

## The fields

| Group | Fields |
|---|---|
| Database | `database_url`, `database_user`, `database_password`, `database_host`, `database_port`, `database_name`, `database_schema` |
| LLM | `llm_model`, `llm_diet_mode`, `llm_timeout_seconds`, `llm_base_url`, `openai_api_key` |
| FLAPI | `flapi_username`, `flapi_token`, `flapi_verify_tls` |
| Limits | `max_parallel_workflows`, `package_timeout_seconds`, `conversation_retention_days`, `log_retention_days` |
| Session | `cookie_secret` |
| Paths | `runtime_settings_file`, `request_log_path` |

Notable defaults: the LLM is `gemma4:31b-cloud` at `http://localhost:11434/v1`
(local Ollama — from inside the backend container use `http://pghost:11434/v1`),
`llm_diet_mode` is on, and both model and package timeouts are 120 seconds.

The explicit database fields override whatever the URL carries; empty means
"not set". `database_schema` may also arrive as `?currentSchema=` inside a JDBC
URL — see the runtime-settings docs for that translation.

`openai_api_key` uses `validation_alias="OPENAI_API_KEY"`, so it reads the
conventional unprefixed variable rather than `AISUMMRY_OPENAI_API_KEY`.

The service holds **no caller credential**: there is no password login and no
API token, so every FDE route is unauthenticated and the deployment must be
reachable only from a trusted network. `cookie_secret` signs the anonymous
conversation session cookie, which identifies a chat history but grants no
privileges.

## Rules

- `extra="ignore"` — unknown env vars never crash startup.
- Every field needs a default, so the app boots on a clean machine.
- Adding a user-editable setting means adding it in **three** places: here,
  the `RuntimeSettings` dataclass, and the store's constructor. Add it to
  `_SECRET_FIELDS` too if it is a credential.
- Secrets are never returned by the API; the store masks them.
