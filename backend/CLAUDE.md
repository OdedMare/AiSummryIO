# AiSummryIO backend context

Read this before changing `backend/`.

**[INDEX.md](INDEX.md) maps every directory to its own `CLAUDE.md`** — use it
to jump straight to the layer you are working in. The FLAPI/`flunks` adapter
is documented in depth in
[app/dal/providers/flapi/CLAUDE.md](app/dal/providers/flapi/CLAUDE.md).

## Purpose

The backend turns one opaque string identifier into a traceable Hebrew
summary. An initial request runs all published `baseline`/`both` workflows.
Follow-ups reuse conversation evidence and run one relevant
`detail`/`both` workflow or one FDE-approved standalone tool when needed.
A follow-up is resolved against the conversation's prior turns first, so a
question that names its subject only by reference can still be routed.

## Runtime and commands

Python is exactly **3.8.10**, matching LocatoAI. Keep annotations compatible:
use `Optional`, `List`, and `Dict`; do not use `X | Y`, `list[str]`, or
`match`.

```bash
cd backend
python -m pytest -q
uvicorn app.main:app --reload
```

## Architecture

- `common/` — env defaults plus the live `runtime-settings.json` override
  store. Saved settings override env without restart; secrets are masked.
- `dal/database/postgres.py` — PostgreSQL connection and schema creation.
- `dal/llm/` — LocatoAI's OpenAI-compatible JSON client and degradation
  ladder. Keep model/base URL/API key live per call.
- `dal/providers/flapi/` — FLAPI Flow Package adapter through `flunks`.
  Identifiers are opaque strings and enter `PackageInputCube.values`; never
  coerce them to integers. Package output is generic structured data;
  geometry is optional and rows must never be dropped for lacking it.
  - `provider.py` — run one package, normalize, retry once. Nothing else.
  - `mapper.py` — translate package definitions to/from `flunks` models.
  - `runner_config.py` — timeout policy and `FlapiConfig` construction.
    `verify_tls` is passed only when the installed `flunks` exposes such a
    field.
- `dal/repository/` — the only SQL owner.
- `bl/workflow_engine.py` — `SummaryService`: execution, one retry, partial
  success, evidence retention, section summaries, and final synthesis. A
  workflow's `output_schema` extends the shared section contract; extras are
  returned under `section.fields`. It also owns standalone tool routing and FDE
  workflow planning. Tool inspection runs exactly one identifier, returns a
  bounded preview, infers a reviewable output schema, and asks the model for
  bounded editable metadata suggestions without persistence. A package field
  marked `x-summary: false` in that schema stays in raw evidence but is omitted
  from the facts sent to summary synthesis.
- `bl/prompts/` — prompt text as markdown, loaded by `prompts.load(name)`,
  replacing the former `planning_prompts.py` constants. **FDE-owned content
  stays in the `agent_content` table** — Skills, the `workflow-planner` prompt,
  and a workflow's `system_prompt` are edited live in Agent Studio and must not
  move into files. See [app/bl/prompts/README.md](app/bl/prompts/README.md).
- `bl/workflow_engine_pkg/specialists.py` — bounded leader/worker
  orchestration over published specialists. A leader delegates a focused task
  to at most two specialists; each worker plans only against the workflows and
  Skills assigned to it; the leader then reviews and may ask follow-up
  questions for up to `agent_max_rounds` rounds before synthesis. Active only
  when `agent_max_rounds > 0` — at 0 the existing summary path runs unchanged.
- `bl/workflow_engine_pkg/history.py` — conversation memory: the thread's
  recent turns, and the follow-up restated to stand alone before routing.
  The user's original wording is what is stored and shown; the rewrite is
  internal, and every failure path falls back to the question as typed.
- `bl/jobs.py` — `JobRunner`: bounded background queue. Interactive follow-ups
  have priority. A daemon watchdog reports in-flight runs every 15s, names any
  past 180s as stuck, and purges expired conversations every 5 minutes.
  `capacity()` is exposed so a health check can compare it against threads
  abandoned to FLAPI timeouts.
- `common/logging_setup.py` — logging configuration and the `trace(name)`
  logger factory, called from `main.py` **before any other logger is
  constructed** so no start-up line is lost. Also owns `abandoned_workers()`.
- `api/` — Pydantic HTTP contracts and signed authentication.
- `main.py` — FastAPI routes and composition root.

Business logic lives under `bl/` and data access under `dal/`, mirroring
LocatoAI. A file owns one class or one concern; split rather than append.

## Locked rules

- The agent may select only published, version-pinned workflows or the latest
  FDE-approved standalone tool version. It never invents package calls, HTTP,
  SQL, or mappings.
- Workflow planning creates a draft from catalog tool-version IDs or describes
  a missing tool contract; it never publishes automatically.
- A workflow input may reference `workflow.id`, `workflow.boundaries`, a saved
  `workflow.value`, or an earlier step output. `workflow.boundaries` is the
  area drawn on the map,
  serialized by `common/geometry.py` to an OGC `MULTIPOLYGON` WKT string and
  passed into `PackageInputCube.values` like any other opaque identifier. A
  step that requests it fails clearly when no area was drawn.
- Package input mode is `single` or `many`; both preserve strings.
- Claims require evidence references. Package failures stay visible and do
  not discard successful sections.
- A section returns `coverage`, `patterns`, and `outliers` alongside `facts`,
  and the final summary opens with a `headline`. Distributions are kept apart
  from individual facts so a 300-record split does not read as the equal of one
  record. A section the model failed to produce is marked `degraded: true`
  rather than passed off as a thin result.
- Summary synthesis receives whole `rows` plus `stats` computed in Python over
  every row — frequency, ranges, and emptiness are arithmetic, so deriving them
  in code is exact and cannot be hallucinated. The model states counts from
  `stats`; it never counts for itself.
- `_safe_section` deliberately withholds `evidence_ids` from the final-summary
  model, so the summary is traceable only at section granularity. Per-claim
  citations would require changing what that call receives — do not render them
  in the UI until it does.
- A plan interview asks one question per turn, carrying its own recommendation
  and optionally two to four clickable `options` whose first entry *is* that
  recommendation. `options` must be empty when the honest answers are not
  enumerable; free text stays available on every turn.
- `focus_field` scopes an interview to one form field, and each planner writes
  back only the field it names. Applying a whole draft from a single-field
  conversation would overwrite text the FDE edited by hand elsewhere.
- A follow-up's rewrite never replaces what the user typed. `run["question"]`
  and every rendering of it stay the original wording; only what the model
  reads downstream is resolved. A failed, empty, or declined rewrite routes
  the original question rather than failing the run.
- Conversation history is derived from `summary_runs`, never stored in a
  second table, and only finished runs become turns.
- **Agent mode is bounded on purpose.** At most 2 specialists per question and
  3 workflows overall; `agent_max_rounds` is clamped to 0–5 in both settings
  and the runtime store. Raise the caps only after load tests show the extra
  breadth improves answers — otherwise one question multiplies into dozens of
  model and FLAPI calls. A leader routing failure must fail *small*: it falls
  back to one specialist, never to assigning all of them.
- `agent_max_rounds = 0` must keep the pre-agent summary path byte-for-byte
  intact; there is a test pinning exactly that.
- `llm_timeout_seconds` bounds **one** HTTP completion, not a whole logical
  call — the degradation ladder and the parse retry above it each get their
  own, so a pathological call can take a multiple of it. It exists to stop a
  hung model server from holding a worker for the SDK's 600s default.
- Never log API keys, tokens, raw package bodies, or full user IDs. Diagnostic
  logging of outbound credentials is masked; there is a test asserting it.
- Unhandled exceptions are logged with a full traceback and returned as JSON.
  Starlette's default is a bare non-JSON "Internal Server Error", which the
  client then fails to parse — leaving a 500 with no cause on either side.
- The run poll (`/api/runs/{id}`, every 1.5s) is traced at DEBUG only. At INFO
  it buries every other line.
- There is no authentication: FDE routes are open and the service must be
  deployed on a trusted network only. Anonymous conversation sessions still
  use an HttpOnly signed cookie.
- FDE edits create drafts. Publishing is blocked by invalid mappings or
  failing mandatory examples.
- Keep the design simple: add a module only when it owns a distinct boundary.
