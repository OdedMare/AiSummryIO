# LLM client (`app/dal/llm/`)

An OpenAI-compatible JSON-mode client. The main model is **Gemma 4 31B served
through Ollama**, but the same code works against OpenAI itself, vLLM, Groq,
and other compatible gateways.

Model, API key, and base URL are read from the runtime settings store on
**every call**, so a change saved in the UI settings panel applies immediately
without a restart.

## Files

| File | Lines | Role |
|---|---|---|
| `openai_client.py` | 159 | `OpenAIJsonClient` — the only class callers use |
| `completion_retry.py` | 26 | Transient-failure retry around one API call |
| `json_response_parser.py` | 24 | `extract_json` — strips fences, finds the object |
| `message_merger.py` | 9 | Folds the system prompt into the user turn |
| `model_id_extractor.py` | 16 | Pulls model IDs out of a `/models` response |

Each helper is separate because each handles a different failure of
"OpenAI-compatible" servers that are only approximately compatible.

## `complete_json(system, user, schema=None) -> dict`

The one method that matters. Returns a parsed JSON object, adding a `_usage`
key with token counts when the server reports them.

Two robustness layers stack:

**1. The degradation ladder** (`_attempts`) — tried in order, dropping to the
next on `BadRequestError`:

1. `response_format: json_schema` with the caller's schema
2. `response_format: json_object` (plain JSON mode)
3. no `response_format` at all
4. same, but with the system prompt merged into the user turn — some Gemma
   deployments reject a `system` role outright

Only a `BadRequestError` advances the ladder; any other exception becomes an
`AgentError` immediately. If every rung fails, the last `BadRequestError` is
reported.

**2. The parse retry** (`_MAX_JSON_ATTEMPTS = 2`) — if the reply is not valid
JSON, the bad reply and a correction instruction are appended to the messages
and the whole ladder runs once more. Two failures raise
`AgentError("המודל החזיר JSON לא תקין פעמיים: ...")`.

The whole logical call shares the `llm_timeout_seconds` wall-time budget,
including every ladder rung and retry. The SDK's automatic retries are off;
`completion_retry.py` owns the single visible retry so attempts do not
multiply underneath the application.

`llm_diet_mode` caps completions at `_DIET_MAX_COMPLETION_TOKENS = 1200` and
is on by default.

## Connection reuse

`_client_for(api_key, base_url)` caches one `OpenAI` client keyed by
`(api_key, base_url)`. A fresh client per call paid a TCP/TLS handshake on
every LLM round-trip of a workflow. The cache re-keys automatically when
settings change mid-session, because the store is still read per call.

## Local-server accommodations

- **No API key is required when `llm_base_url` is set.** Local servers ignore
  auth; the SDK still demands a non-empty string, so
  `_LOCAL_SERVER_KEY_PLACEHOLDER = "null"` is sent.
- `list_models()` calls `/models` over raw `httpx` rather than the SDK, so the
  admin UI can probe a candidate endpoint before saving it — it accepts
  `base_url_override` / `api_key_override` for exactly that. The overrides
  arrive from `POST /api/models` (`ModelsProbeRequest`), which the settings
  panel calls with the values currently typed in the form; `GET /api/models`
  uses the saved settings. A secret the user did not retype comes back masked
  and is treated as absent, so the stored key is used.
- Base URLs are normalized before storage: a pasted
  `.../chat/completions` has the operation suffix stripped, because the SDK
  appends the path itself and would otherwise 404. See
  `normalize_llm_base_url` in
  [common/runtime_settings/normalizers.py](../../common/runtime_settings/normalizers.py).

## Rules

- Errors leaving this package are `AgentError` in Hebrew.
- Never log API keys or full prompts containing user identifiers.
- Adding a rung to the ladder means adding it to `_attempts` — do not scatter
  fallback logic through `_complete`.
