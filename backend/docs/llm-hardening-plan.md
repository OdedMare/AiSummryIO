# LLM layer hardening plan

Porting the ideas worth taking from `spear_presenton`'s `LLMClient` into
`app/dal/llm/`. Five changes, independent, ordered by value-per-risk.

Not included: streaming and `AsyncOpenAI`. The backend is synchronous and every
one of the 12 `complete_json` call sites is one-shot JSON. Adopting those would
mean an async rewrite for capability nothing currently asks for. Stronger JSON
repair (`dirtyjson`/`json_repair`) was considered and dropped — it adds a
dependency for failures the existing fence-strip plus brace-find already covers
in practice.

Changes 4 and 5 cover the two "pulling" techniques and are specified after the
first three. **They are not equally recommended** — read change 5's "Why this
may be the wrong thing to build" before starting it.

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

---

## Change 4 — The `ResponseSchema` rung (pulling structured data out)

**The technique.** `spear_presenton` at `llm_client.py:287-300` declares a
synthetic tool named `ResponseSchema` whose `parameters` *are* the caller's
JSON schema, with a handler that does nothing (`do_nothing_async`). The model
"calls" it, and the client reads the object out of
`tool_call.function.arguments` (`:361-366`) rather than `message.content`.

No tool is ever executed. It is purely a way to get schema-enforced JSON from a
model that supports **tool calling** but not **`response_format`** — a real and
common gap, especially on Ollama and older gateways.

**Why it fits here.** This is the one genuine hole in `_attempts`. Today's
ladder degrades from `json_schema` straight to `json_object` to unconstrained
prose, so a model without `response_format` support loses schema enforcement
entirely and falls back on `extract_json` scraping a brace out of free text.
The `ResponseSchema` rung keeps enforcement for exactly those models.

It is also **synchronous-compatible**: no tool is executed, so there is no
handler dispatch, no `asyncio.gather`, and no recursion. It is one more dict in
the `_attempts` list plus a branch in response reading.

**Change.**

`openai_client.py`:
- `_attempts` gains a final rung, after the four existing ones:

  ```python
  {
      "messages": messages,
      "tools": [{
          "type": "function",
          "function": {
              "name": "ResponseSchema",
              "description": "Provide response to the user",
              "parameters": schema,
          },
      }],
      "tool_choice": {
          "type": "function",
          "function": {"name": "ResponseSchema"},
      },
  }
  ```

  Added only when `schema is not None` — with no schema there is nothing to
  enforce and the plain rungs already cover it.

  `tool_choice` is forced rather than `"auto"`. Their version leaves it open
  and then copes with the model answering in prose anyway; forcing it removes
  that branch entirely.

- `_response_data` must now read either `message.content` **or**
  `message.tool_calls[0].function.arguments`. Prefer the tool call when
  present. This is the only real change to response handling, and it is where
  the risk sits — it is on the path every rung returns through.

**Ordering.** Last rung, not first. Rungs 1-2 are cheaper and more widely
supported; this one is the fallback for models that reject both. Note it lands
*after* the system-merge rung, so a model needing both accommodations is still
covered — the merge rung's failure advances into this one.

**Interaction with change 2.** `prefers_schema_rung` currently gates rung 1. If
a model rejects `json_schema` but supports tools, the useful configuration is
"skip rung 1, keep rung 5". Keep the capability flags separate — do not
collapse them into one boolean.

**Tests.**
- A server rejecting rungs 1-4 with `BadRequestError` succeeds on the
  `ResponseSchema` rung, and the parsed object comes from
  `tool_calls[0].function.arguments`.
- `schema=None` never emits the rung.
- `tool_choice` names `ResponseSchema` exactly.
- A response carrying *both* content and a tool call prefers the tool call.

---

## Change 5 — The recursive tool-execution loop

**The technique.** `spear_presenton`'s `_generate_openai` (`:158-210`) is
genuinely agentic: when the model returns tool calls, it dispatches every
handler concurrently through `asyncio.gather`
(`llm_tool_calls_handler.py:95`), appends the assistant message plus one
`tool` message per result, and **calls itself with `depth + 1`**, looping until
the model stops asking. Tools are registered in a `tools_map`
(`GetCurrentDatetimeTool`) or supplied per call as `LLMDynamicTool`.

### Why this may be the wrong thing to build

Read this before starting. `AiSummryIO` **already solves this problem a
different way, deliberately**, and the two designs are in direct tension:

- **Your router picks one tool, in one call, from a validated catalog.**
  `select_detail` (`routing.py:126`) sends `available_tools` in the payload and
  gets back a `tool_version_id` under `ROUTER_SCHEMA` (`schemas.py:335`), which
  is then checked against the real catalog by `_validated_plan`. The model
  *names* a tool; your code decides whether to run it.

- **A native tool loop inverts that.** The model would emit `tool_calls` that
  execute on return. That collides head-on with the locked rule in
  `backend/CLAUDE.md`: *"The agent may select only published, version-pinned
  workflows or the latest FDE-approved standalone tool version. It never
  invents package calls."* A native loop is precisely a mechanism for the model
  to invent calls, and the FDE approval gate is what would be bypassed.

- **Your tools are not free functions.** They are FLAPI packages behind
  `input_mode`, per-package timeouts, `run_bounded`, retry, and evidence
  persistence. `_run_package` is not something a `tools_map` handler can
  stand in for.

- **`asyncio.gather` has no sync equivalent here.** Their concurrency is
  async; yours is `ThreadPoolExecutor` bounded by `max_parallel_workflows`.
  Fan-out would have to be rebuilt on threads.

- **Their loop has no depth ceiling.** `depth` only gates one-time setup; a
  model that keeps calling tools recurses without bound. Any port must add a
  ceiling their version lacks.

**Recommendation: do not port this as-is.** The routing you have is stricter,
auditable, and enforces the approval gate. Replacing it with a native loop
would trade those for flexibility the product does not currently need.

### If you want it anyway — the narrow version

There is one defensible shape, and it is **not** "let the model run packages":

Keep `_run_package`, evidence, and the FDE gate exactly as they are. Add tool
calling only for **read-only, side-effect-free helpers** that do not touch
FLAPI — the `GetCurrentDatetimeTool` category. Concretely:

- New `app/dal/llm/tool_loop.py` — one concern: given messages and a registry
  of `name -> callable`, run the request/dispatch/append cycle until the model
  stops or a ceiling is hit.
- **`_MAX_TOOL_DEPTH = 3`, enforced.** On exceeding it, raise `AgentError` in
  Hebrew rather than looping. This is the guard their version is missing.
- **A registry allowlist.** A tool name not in the registry is an error, never
  a dynamic lookup. This preserves "never invents calls" at the client
  boundary.
- Sequential dispatch first. Threads only if a real call site needs fan-out —
  do not port `gather` speculatively.
- `complete_json` keeps its current signature. The loop is opt-in through a new
  method or an explicit `tools=` argument, so all 12 existing call sites are
  untouched.

Even this is speculative: **no current call site needs it.** I would build it
when a concrete feature requires the model to fetch something mid-reasoning,
not before.

---

## Order and risk

**Change 1** (retry classification, `completion_retry.py`) is low risk — it
widens an exception tuple that already exists.

**Change 3** (usage logging, `openai_client.py`) is low risk — observability
only, no behaviour change.

**Change 2** (capability adaptation, new `model_capabilities.py` plus
`openai_client.py`) is medium risk — it makes ladder construction conditional
on the model id.

**Change 4** (`ResponseSchema` rung, `openai_client.py`) is medium risk — the
new rung itself is additive, but reading the response from either `content` or
`tool_calls` sits on the path every rung returns through.

**Change 5** (tool-execution loop, new `tool_loop.py` plus callers) is high
risk and **not recommended** — it conflicts with a locked rule.

Changes 1-4 are independent; any subset ships alone. Suggested order is
1, 3, 2, 4 — the cheap fix and the visibility first, so changes 2 and 4's
effect on rung selection is observable in the logs the moment they land.

Change 5 is specified for completeness, not recommended. It should not be
started without an explicit decision to revisit the agent-selection rule in
`backend/CLAUDE.md`, and that decision is the FDE's, not an implementation
detail.

## Docs to update

- `app/dal/llm/CLAUDE.md` — the file table (new modules), the fixed
  `_MAX_JSON_ATTEMPTS = 2` claim, and the ladder description: it documents
  exactly four rungs, which change 4 makes five and change 2 makes
  conditional.
- `backend/CLAUDE.md` — only if change 5 is ever pursued, since it edits a
  locked rule.

## Verification

`cd backend && python -m pytest -q`

Note: local Python is 3.13.9 while the project pins 3.8.10. Tests running
clean locally does **not** prove 3.8 compatibility — no `match`, no `X | Y`, no
builtin generics in any new code. Worth a targeted grep before calling it done.
