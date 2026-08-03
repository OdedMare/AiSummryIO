# Tests (`tests/`)

One file, `test_core.py`, covering the rules that are expensive to
get wrong. Run from `backend/`:

```bash
python -m pytest -q
```

## What is covered

| Area | Rule under test |
|---|---|
| FLAPI mapper | String identifiers survive; generic rows; duplicate columns rejected; empty frames |
| FLAPI provider | Retries exactly once; `_package_query` provenance; timeout bounds the run |
| `runner_config` | Timeout precedence; `FlapiConfig` built for both modern and legacy classes |
| Geometry | Drawn area reaches the package as `MULTIPOLYGON` WKT; missing area fails clearly; rings must be closed |
| Workflow validation | No forward step references; `depends_on` must be declared |
| Conversational planning | Draft carries forward between turns; sample data stays bounded and drops internals; a chat draft still passes the shared validation gate |
| Conversation memory | An opening follow-up pays for no rewrite; a reference is resolved against the thread; the user's wording is what is persisted; every rewrite failure routes the original question; the router sees the thread only when there is one |
| Identifier mapping | Fan-out over list values plus deduplication |
| Settings | URL/schema normalization, JDBC translation, secret masking |
| Auth | scrypt hashing and verification |

## Testing without `flunks`

`flunks` is not on PyPI and is not installed in CI, so
`_install_fake_flunks(monkeypatch)`
([test_core.py:34](test_core.py#L34)) injects stub modules into `sys.modules`.
Every flunks model becomes a permissive attribute bag:

```python
class Model:
    def __init__(self, **values):
        self.__dict__.update(values)
```

This works because the provider imports `flunks` **lazily, inside functions** —
patching `sys.modules` before the call is enough. Keep it that way.

For the runner itself, prefer the injection seam over patching internals:

```python
provider = FlapiProvider(store, runner_factory=lambda settings, config: FakeRunner())
```

`runner_factory` receives `(settings, package_config)` and returns anything
with a `.run()` method returning a DataFrame.

## Conventions

- **Test names state the rule**, not the method
  (`test_a_step_scoped_to_the_map_fails_clearly_without_a_drawn_area`).
- Hebrew error messages are asserted with `pytest.raises(..., match=...)`.
  Rewording a user-facing error is a behavior change and will fail here.
- Timing tests assert generous bounds (the timeout test allows 10s for a 1s
  timeout over two attempts) so they stay stable on a loaded machine.
- Fakes are defined inline in the test that needs them. `conftest.py` holds
  only the `flunks` stubbing, which must run before collection.

## Python version

Exactly **3.8.10**, matching LocatoAI. No `X | Y` annotations, no `list[str]`,
no `match`. Use `Optional`, `List`, `Dict`.
