# LLM layer hardening plan

Porting the ideas worth taking from `spear_presenton`'s `LLMClient` into
`app/dal/llm/`. Three changes, independent, ordered by value-per-risk.

Not included: streaming, tool calling, and `AsyncOpenAI`. The backend is
synchronous and every one of the 12 `complete_json` call sites is one-shot
JSON. Adopting those would mean an async rewrite for capability nothing
currently asks for. Stronger JSON repair (`dirtyjson`/`json_repair`) was
considered and dropped — it adds a dependency for failures the existing
fence-strip plus brace-find already covers in practice.

## Constraints that shaped this

- **Python 3.8.10.** No `match`, no `X | Y`, no `list[str]`. Use `Optional`,
  `List`, `Dict`.
- **Synchronous.** No `async def` outside `main.py`'s FastAPI handlers.
- **Hebrew user-facing errors.** `AgentError` messages stay Hebrew; log lines
  stay English.
- **Never log** API keys, tokens, raw bodies, or full user identifiers.
- **One class or concern per file.** Split rather than append.

---

## Change 1 — Retry classification and 5xx

**Problem.** `completion_retry.py:7` retries exactly three exception types:

```python
_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError)
```

`InternalServerError` is absent, so a 503 or 502 from Ollama — the single most
likely transient failure for a locally served model under load — fails on the
first attempt with no retry at all. The delay is also flat (`0.3s` twice),
which does not help a server that needs a moment to recover.

`spear_presenton` has the right idea in `should_retry_error`
(`utils/llm_retry.py:257`) but wires it wrong: `retry_with_backoff` catches
bare `Exception`, so it burns five attempts with 2.5x backoff on a 401 that
will never succeed. Take the classification, not the wiring.

**Change.** `app/dal/llm/completion_retry.py`:

- Add `InternalServerError` to `_ERRORS`.
- Add `APIStatusError` guarded by `status_code >= 500`, so 502/503/504 from
  gateways that do not map onto the SDK's typed errors are also caught. A 4xx
  `APIStatusError` must *not* retry — that is the bug being avoided.
- Replace the flat delay with exponential backoff: `0.3s`, `0.9s` (factor 3),
  capped. Keep `_ATTEMPTS = 2` by default.
- Explicitly never retry `BadRequestError` — the degradation ladder in
  `_attempts` owns that failure, and retrying here would multiply every rung.

**Interaction to be careful about.** `_complete` advances the ladder on
`BadRequestError`. If retry starts swallowing a broader class of errors, a rung
that should fail fast could stall. Keeping `BadRequestError` explicitly
non-retryable preserves the current ladder timing exactly.

**Worst case.** Two attempts x four ladder rungs x two parse attempts = 16 API
calls. That is unchanged from today's ceiling; only *which* errors reach it
changes.

**Tests.** `tests/test_core.py`:
- 5xx `APIStatusError` retries and then succeeds.
- 4xx `APIStatusError` raises immediately, one call only.
- `BadRequestError` is not retried here and still advances the ladder.

---

## Change 2 — Model-capability adaptation

**Problem.** `_MAX_JSON_ATTEMPTS = 2` is a module constant applied identically
to every model. Gemma 4 31B via Ollama and GPT-4o do not fail the same way or
at the same rate, but they currently get the same two attempts.

This is `spear_presenton`'s best idea — `is_small_model` / `get_max_retries` /
`should_use_strict_json` from `utils/model_capabilities`, consumed at
`llm_client.py:465-467`. Their version is async and feeds a retry helper; ours
feeds the existing ladder and parse loop instead.

**Change.** New file `app/dal/llm/model_capabilities.py`, one concern:

```python
def max_json_attempts(model: str) -> int
def prefers_schema_rung(model: str) -> bool
```

Derived from the model id by substring match — `gemma`, `qwen`, `phi`,
`llama`, `mistral`, and any `:Nb` tag under a threshold read as small. Small
models get 3 parse attempts instead of 2. Unknown models keep today's
behaviour of 2, so this is additive, never a regression.

`prefers_schema_rung` addresses a real cost: for a model that reliably rejects
`json_schema`, rung 1 is a guaranteed wasted round-trip on every single call.
Returning `False` starts the ladder at `json_object`. `_attempts` already takes
`schema`, so this is a filter on the list it builds — no new fallback path,
which is what `dal/llm/CLAUDE.md` requires.

**Wiring.** `openai_client.py`:
- `complete_json` reads `settings.llm_model`, asks for `max_json_attempts`,
  uses it as the loop bound in place of the constant.
- `_attempts` takes the `prefers_schema_rung` result and drops rung 1 when it
  is `False`.
- Keep `_MAX_JSON_ATTEMPTS = 2` as the documented fallback for unknown models.

**Deliberately not ported.** Their `strict` / `ensure_strict_json_schema`
distinction. Our ladder never sets `strict` on the `json_schema` rung, so
there is no strict mode to relax — adding one would be new behaviour, not a
port.

**Tests.**
- A `gemma` model id gets 3 attempts; `gpt-4o` gets 2; unknown gets 2.
- `prefers_schema_rung` False omits the `json_schema` rung and the first call
  goes out as `json_object`.
- Ladder order is otherwise unchanged.

---

## Change 3 — Usage and latency logging

**Problem.** `complete_json` already accumulates a `usage` dict across attempts
and attaches it as `result["_usage"]` (`openai_client.py:51,60-65`) — but
nothing logs it. Token cost and latency are invisible, and so is *which rung
succeeded*, which is the single most useful diagnostic this layer has. A model
silently failing rung 1 on every call looks identical to one succeeding on it.

The FLAPI provider already sets the house pattern for this
(`providers/flapi/provider.py:35-39,79-81`): announce the call, log elapsed and
row count on return.

**Change.** `openai_client.py`, mirroring that pattern:
- `_complete` returns which rung index succeeded alongside content and usage.
- `complete_json` logs once per call at INFO: model, rung reached, parse
  attempts used, prompt/completion/total tokens, elapsed seconds.
- Log a WARNING when the ladder degrades past rung 1 — that is the signal the
  configured model does not support what is being asked of it.
- English log lines. No prompts, no completions, no keys. Token *counts* only.

`_usage` in the returned dict stays exactly as is — call sites may read it.

**Tests.**
- A successful call logs model, rung, and token counts (via `caplog`).
- Degrading past rung 1 emits a WARNING.
- No log record contains the api key or any prompt text.

---

## Order and risk

| # | Change | Files | Risk |
|---|---|---|---|
| 1 | Retry classification | `completion_retry.py` | Low — widens an existing set |
| 2 | Capability adaptation | new `model_capabilities.py`, `openai_client.py` | Medium — touches ladder construction |
| 3 | Usage logging | `openai_client.py` | Low — observability only |

Independent; any subset ships alone. Suggested order is 1, 3, 2 — get the
cheap fix and the visibility in first, so change 2's effect on rung selection
is observable in the logs the moment it lands.

## Docs to update

- `app/dal/llm/CLAUDE.md` — the file table (new module), the fixed
  `_MAX_JSON_ATTEMPTS = 2` claim, and the ladder description if rung 1 becomes
  conditional.

## Verification

`cd backend && python -m pytest -q`

Note: local Python is 3.13.9 while the project pins 3.8.10. Tests running
clean locally does **not** prove 3.8 compatibility — no `match`, no `X | Y`, no
builtin generics in any new code. Worth a targeted grep before calling it done.
