# FLAPI provider (`app/dal/providers/flapi/`)

The adapter between this app and **FLAPI Flow Packages**, reached through the
internal **`flunks`** library. This is the only place in the backend that
imports `flunks`. Everything above it (`bl/workflow_engine.py`) sees plain
`List[dict]` rows and never learns that cubes exist.

Read this before touching anything here — several rules below exist because
breaking them produced silent data loss, not a crash.

## What FLAPI and flunks actually are

**FLAPI** is the internal data platform. A **Flow Package** is a pre-built,
version-pinned query living inside it, identified by a `package_id`. A package
takes an **input cube** (a named parameter plus a list of values) and produces
an **output cube** (a table of results). The app never writes SQL or HTTP
against FLAPI; it can only invoke packages that already exist there.

**`flunks`** is the internal Python client for FLAPI. It is **not on PyPI**, so
it is supplied either as a wheel dropped into `backend/wheelhouse/` (wheels are
gitignored — only the README and pin file are tracked) or from the internal
index at build time. See [wheelhouse/README.md](../../../../wheelhouse/README.md).

It is imported **lazily — inside functions, never at module top level** — so
the app boots, tests run, and the admin UI works on a machine with no wheel
installed. A missing wheel surfaces as a Hebrew `ProviderError` on the first
package call, not an `ImportError` traceback at startup.

> The image build runs `import flunks` right after install, so a broken wheel
> fails the build. That check exists because the `FlapiConfig` / `FlApiConfig`
> capitalization typo once reached `main` — hence the emphasis on the capital
> `A` below.

The flunks objects used here:

| Object | Module | Role |
|---|---|---|
| `FlunksRunner` | `flunks` | Executes a package. Only method used: `.run()` |
| `FlApiConfig` | `flunks.config` | Credentials + TLS. **Capital `A`** — matches LocatoAI |
| `FlunksConfig` | `flunks.config` | Runner-level options; constructed empty |
| `FlunksPackageConfig` | `flunks.config` | One package invocation |
| `PackageInputCube` | `flunks.flow_models` | `cube_name`, `cube_parameter`, `values` |
| `PackageOutputCube` | `flunks.flow_models` | `cube_name` |

`FlunksRunner.run()` returns a **pandas DataFrame**. It offers **no
cancellation** — this single fact is why `run_bounded` exists.

## The three files

A package run crosses them in this order:

```
workflow_engine._run_package(package, identifiers)
        │
        ▼
provider.FlapiProvider.run(package, identifiers)     ← retry policy
        ├── mapper.package_config(package, ids)      → FlunksPackageConfig
        ├── runner_config.resolve_timeout(pkg, cfg)  → int seconds
        ├── provider._runner(config)                 → FlunksRunner
        │       └── runner_config.build_flapi_config(FlApiConfig, settings)
        ├── runner_config.run_bounded(runner, t, key) → DataFrame
        └── mapper.normalize(result)                 → List[dict]
```

### `provider.py` — orchestration and retry, nothing else

`FlapiProvider.run()` runs one package, normalizes, and retries **once**
(`_ATTEMPTS = 2`). Each method does one thing:

- `run` — the retry loop only. On the final failure raises `ProviderError`
  with `from exc`, so the original traceback survives.
- `_attempt` — one full run: map config → resolve timeout → execute bounded →
  normalize → tag → log.
- `_tag_query` — stamps `_package_query` on every row when the package
  declares a `query_name`. Uses `setdefault`, so real package data of the same
  name is never overwritten.
- `_failure` — logs the exhausted package and builds the Hebrew error.
- `_runner` — picks the injected `runner_factory` (tests) or a real runner.
- `_require_credentials` — username + token must both be present.
- `_flunks_runner` — the lazy `flunks` import and `FlunksRunner` construction.

The `raise AssertionError("unreachable...")` after the loop is deliberate: the
last attempt always returns or raises, and the line documents that instead of
leaving an implicit `return None`.

**The timeout is resolved per attempt, and applies per attempt.** A package
with `timeout_seconds: 30` can therefore occupy ~60s of wall clock across both
attempts. This is intended; it is also why the timeout test asserts the total
stays well under the 120s global default.

### `mapper.py` — translation to/from flunks models

`package_config()` builds `FlunksPackageConfig` from a package row. It filters
identifiers to non-blank strings and raises if none survive — an empty
`values` list would make FLAPI return everything, not nothing.

`normalize()` turns the DataFrame into `List[dict]`, and enforces two rules:

- **Duplicate column names are rejected loudly.** `to_dict("records")` keeps
  only the last column of a repeated name. Since flunks joins cubes, two cubes
  contributing the same name is reachable, and silently dropping one would
  make a summary quietly incomplete. `_reject_duplicate_columns` raises first.
- **Cell coercion order in `_value` is load-bearing.** `None`/`NaN` → `None`;
  then `.wkt` (geometry → WKT string); then `.isoformat()`; then `.item()`.
  Temporal values **must** be checked before `.item()` — `pd.Timestamp` has
  `.item()` but it returns another `Timestamp`, which psycopg's `Jsonb` cannot
  serialize, failing the evidence write for the entire step rather than one
  cell.

### `runner_config.py` — timeout policy and credential shaping

`resolve_timeout(package, settings)` — per-package `timeout_seconds`, else
`settings.package_timeout_seconds`, else 120. Floored at 1.

`run_bounded(runner, timeout, package_key)` — submits `runner.run` to a
single-worker `ThreadPoolExecutor` and waits at most `timeout`. Because flunks
cannot be cancelled, the worker thread **may outlive the timeout**; the pool is
shut down with `wait=False` so the caller is never blocked. Bounding the wait
is what stops one slow package from stalling an entire run.

`build_flapi_config(config_class, settings)` — passes `verify_tls` **only when
the installed flunks version has such a field**, probing `model_fields`
(pydantic v2), `__fields__` (v1), then `__annotations__`. Field names differ
across versions, so `_TLS_FIELDS = ("verify_tls", "verify", "verify_ssl")` is
tried in order. If none exists and TLS verification was disabled, it logs a
warning that the setting is being ignored rather than failing.

## Locked rules

- **Identifiers are opaque strings. Never coerce them to `int`.** They may be
  `"001"` (leading zero significant), `"HOME-A/7"`, or a WKT `MULTIPOLYGON`.
- **A drawn map area is just another identifier.** `common/geometry.py`
  serializes it to OGC WKT and it enters `PackageInputCube.values` unchanged.
- **Never drop a row for lacking geometry.** Package output is generic
  structured data; geometry is optional.
- **Never log tokens, raw package bodies, or full user identifiers.** Logs
  carry `package_key`, row counts, and exception *type* only.
- All user-facing errors are `ProviderError` in **Hebrew**. Tests match on
  these strings — changing the wording breaks them.
- Keep `flunks` imports lazy and inside functions.

## The package dict

Produced by `repository.get_package()`, schema in
[repository/repository.py](../../repository/repository.py), validated by
`PackageCreate` in [api/models.py](../../../api/models.py).

| Key | Used by | Notes |
|---|---|---|
| `package_id` | mapper | FLAPI's ID. Always `str()`-cast |
| `package_key` | provider | Stable slug for logs and versioning |
| `input_cube_name` | mapper | |
| `input_cube_parameter` | mapper | The parameter receiving `values` |
| `output_cube_name` | mapper | |
| `input_mode` | **engine, not provider** | `single` = one call per identifier; `many` = one call for all |
| `query_name` | provider | Optional; drives `_package_query` |
| `timeout_seconds` | runner_config | Optional per-package override |

`input_mode` is applied one level up in
[workflow_engine.py:343](../../../bl/workflow_engine.py#L343) — the provider always
receives a ready list.

## Testing without flunks

`_install_fake_flunks(monkeypatch)` in
[tests/test_core.py:34](../../../../tests/test_core.py#L34) injects stub
modules into `sys.modules`, so every flunks model becomes a permissive
attribute bag. Combined with `FlapiProvider(store, runner_factory=...)`, the
whole provider is testable with no wheel present. Prefer `runner_factory` over
patching internals.

Relevant tests: retry + provenance (`test_flapi_provider_retries_once...`),
timeout bounding (`test_package_run_is_bounded_by_the_configured_timeout`),
duplicate columns, string preservation, and `build_flapi_config` against both
modern and legacy config classes.
