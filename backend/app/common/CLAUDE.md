# Shared utilities (`app/common/`)

Small, dependency-light pieces used across `bl/` and `dal/`. Nothing here
imports from those layers — `common/` is the bottom of the dependency graph.

| Path | Owns |
|---|---|
| `config/` | Env-derived defaults ([config/CLAUDE.md](config/CLAUDE.md)) |
| `runtime_settings/` | The live, user-editable settings store ([runtime_settings/CLAUDE.md](runtime_settings/CLAUDE.md)) |
| `errors.py` | The exception hierarchy |
| `geometry.py` | GeoJSON MultiPolygon → WKT |

## `errors.py`

Every exception carries the HTTP status `main.py` should return, so the
exception handler needs no mapping table.

| Class | Status | Meaning |
|---|---|---|
| `AppError` | 400 | Base; bad input |
| `AgentError` | 502 | The LLM failed or returned unusable output |
| `ProviderError` | 502 | A FLAPI package failed |
| `NotFoundError` | 404 | |
| `AuthError` | 401 | |
| `UnavailableError` | 503 | Alive, but out of capacity to accept work |

Messages are **Hebrew** and user-facing — they reach the UI directly. Several
tests match on them, so rewording is a behavior change.

## `geometry.py`

`multipolygon_to_wkt(boundaries)` converts a GeoJSON `MultiPolygon` dict into
an OGC WKT `MULTIPOLYGON` string, returning `""` when there is no geometry and
raising on any other geometry type.

Why it exists: FLAPI cube parameters accept **opaque strings**, so an area
drawn on the map travels into `PackageInputCube.values` exactly like an
identifier does. See
[dal/providers/flapi/CLAUDE.md](../dal/providers/flapi/CLAUDE.md).

Deliberately **dependency-free** — shapely is not a backend dependency.
`_format` trims coordinates to 7 decimals and strips trailing zeros, which is
what makes the WKT output stable enough to assert on in tests.

Validation of the incoming shape (closed rings, etc.) happens in
`GeoBoundaries` in [api/models.py](../api/models.py), not here.
