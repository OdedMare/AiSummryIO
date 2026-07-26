# Backend documentation index

Where every piece of the backend lives, and which `CLAUDE.md` explains it.
Start at [CLAUDE.md](CLAUDE.md) for the project-wide rules; come here to find
the right directory fast.

## Map

```
backend/
├── CLAUDE.md                 ← project rules, Python version, locked rules
├── INDEX.md                  ← you are here
├── app/
│   ├── CLAUDE.md             ← main.py · repository.py · models.py · auth.py
│   ├── bl/CLAUDE.md          ← SummaryService · JobRunner
│   ├── common/CLAUDE.md      ← errors · geometry
│   │   ├── config/CLAUDE.md            ← env defaults
│   │   └── runtime_settings/CLAUDE.md  ← live settings · normalizers · hashing
│   └── dal/CLAUDE.md         ← database/postgres.py
│       ├── llm/CLAUDE.md              ← OpenAI-compatible JSON client
│       └── providers/flapi/CLAUDE.md  ← FLAPI + flunks (most detailed)
└── tests/CLAUDE.md           ← test conventions · faking flunks
```

## Directory docs

| Doc | Covers | Read it when |
|---|---|---|
| [app/CLAUDE.md](app/CLAUDE.md) | Composition root, routes, SQL, models, auth | Adding an endpoint, changing the schema, wiring a dependency |
| [app/bl/CLAUDE.md](app/bl/CLAUDE.md) | `SummaryService`, `JobRunner` | Changing how workflows run, synthesize, or queue |
| [app/dal/CLAUDE.md](app/dal/CLAUDE.md) | PostgreSQL connections, schema creation | Touching connections or `search_path` |
| [app/dal/llm/CLAUDE.md](app/dal/llm/CLAUDE.md) | LLM client, degradation ladder | Model calls, JSON parsing, a new provider endpoint |
| [app/dal/providers/flapi/CLAUDE.md](app/dal/providers/flapi/CLAUDE.md) | **FLAPI packages via `flunks`** | Anything touching packages, cubes, timeouts, or `flunks` |
| [app/common/CLAUDE.md](app/common/CLAUDE.md) | Errors, geometry → WKT | Adding an error type or changing map serialization |
| [app/common/config/CLAUDE.md](app/common/config/CLAUDE.md) | Env defaults | Adding a setting |
| [app/common/runtime_settings/CLAUDE.md](app/common/runtime_settings/CLAUDE.md) | Live settings, normalizers, password hashing | Settings panel behavior, URL parsing, secrets |
| [tests/CLAUDE.md](tests/CLAUDE.md) | Test conventions, faking `flunks` | Writing or fixing a test |

## Finding things by task

| Task | Go to |
|---|---|
| Connect a new FLAPI package | [flapi/CLAUDE.md](app/dal/providers/flapi/CLAUDE.md), then `PackageCreate` in [models.py](app/models.py) |
| Understand what `flunks` is | [flapi/CLAUDE.md](app/dal/providers/flapi/CLAUDE.md) § *What FLAPI and flunks actually are* |
| Debug a package timeout | `run_bounded` in [runner_config.py](app/dal/providers/flapi/runner_config.py) |
| Debug a package returning wrong columns | `normalize` in [mapper.py](app/dal/providers/flapi/mapper.py) |
| Change retry behavior | `FlapiProvider.run` in [provider.py](app/dal/providers/flapi/provider.py) |
| Add a setting to the admin UI | [config/CLAUDE.md](app/common/config/CLAUDE.md) — three places to edit |
| Fix a JDBC / `currentSchema` URL | `normalizers.py` § in [runtime_settings/CLAUDE.md](app/common/runtime_settings/CLAUDE.md) |
| Change how a summary is written | `_section_summary` / `_final_summary` in [bl/CLAUDE.md](app/bl/CLAUDE.md) |
| Change step input mapping | `_identifiers` in [bl/CLAUDE.md](app/bl/CLAUDE.md) |
| Add an API route | [app/CLAUDE.md](app/CLAUDE.md) § *main.py* |
| Change the database schema | `_SCHEMA` in [repository.py:485](app/repository.py#L485) |
| Add or fix a test | [tests/CLAUDE.md](tests/CLAUDE.md) |

## The request path, end to end

```
POST /api/summaries              main.py
  └── Repository.create_run      repository.py        (queued)
  └── JobRunner.submit           bl/jobs.py           (background)
        └── SummaryService.full_summary               bl/workflow_engine.py
              ├── published_workflows                 repository.py
              └── per workflow: _execute_workflow
                    ├── _identifiers                  → strings / WKT
                    ├── _run_package                  → input_mode fan-out
                    │     └── FlapiProvider.run       dal/providers/flapi/
                    │           └── flunks → FLAPI    (DataFrame → List[dict])
                    ├── save_evidence                 repository.py
                    └── _section_summary              dal/llm/
              └── _final_summary                      dal/llm/
GET /api/runs/{id}               main.py              (poll for the result)
```

## Non-negotiable rules

Full list in [CLAUDE.md](CLAUDE.md). The ones most often broken:

- Python **3.8.10** — no `X | Y`, no `list[str]`, no `match`.
- Identifiers are **opaque strings**; never coerce to `int`.
- SQL lives only in `repository.py`.
- Package failures stay visible and never discard successful sections.
- Never log API keys, admin passwords, raw package bodies, or full user IDs.
- User-facing errors are Hebrew, and tests assert on their wording.
