# Using the AiSummryIO API from a script

This is the reference for talking to the backend directly over HTTP — not
through the browser UI. It documents the contract as implemented in
`backend/app/api/` and `backend/app/api/routers/`, and pairs with
[`backend/scripts/run_multipolygons.py`](backend/scripts/run_multipolygons.py),
which runs a batch of drawn areas (GeoJSON `MultiPolygon`s) against the API
and collects one summary per area.

The service has **no authentication** — every route is open and it is meant
to be reached only from a trusted network (see `backend/CLAUDE.md`). There is
nothing to log in with; the one thing a script must still get right is the
session cookie described below.

## Base URL and versioning

Every route is served twice:

| Prefix | For |
|---|---|
| `/api` | the bundled frontend |
| `/api/v1` | programmatic clients — same handlers, stable path |

Use `/api/v1` from a script. Locally that's `http://localhost:8000/api/v1`
(`docker compose up` / `uvicorn app.main:app --reload`); behind the optional
nginx proxy it's `http://<host>/api/v1`.

Interactive docs: `GET /docs` (Swagger UI) and `GET /openapi.json`.

## The one thing that trips up a script: the session cookie

A "conversation" (one identifier or area, plus every question asked about
it) belongs to whoever's `aisummry_session` cookie created it. The cookie is
`HttpOnly`, signed, and issued by **every** response — `POST /summaries` sets
it, and it must come back on every later call that touches the same
conversation (`GET /runs/{id}`, `GET /runs/{id}/evidence`,
`POST /conversations/{id}/messages`).

If it doesn't come back, the server has no anonymous credential to fall back
to: it mints a fresh random session for that call, the ownership check
(`conversation.session_id == caller's session_id`) fails, and you get
`404 {"detail": "הפריט לא נמצא"}` — which reads exactly like "wrong run id"
even though the run exists. This is not a bug to route around in the API; the
isolation is intentional (one caller cannot list or poll another caller's
runs). The fix is entirely client-side:

- **Browser**: automatic, cookies persist across requests.
- **`curl`**: `-c cookies.txt -b cookies.txt` on every call in the sequence.
- **Python `requests`**: use a `requests.Session()` object, not bare `requests.get/post`.
- **Python `httpx`**: use an `httpx.Client()`, or capture the cookie from the
  `POST /summaries` response and pass it explicitly on later calls.

**For a batch of independent runs (this is the multipolygon case) don't share
one cookie jar across concurrent requests** — two runs submitted at the same
moment through one shared client will race to overwrite each other's cookie,
and whichever run's polling loses the race gets 404s. `run_multipolygons.py`
captures each run's cookie right off its `POST /summaries` response and pins
it to that run's own polls, so concurrent runs never collide. See
[Concurrency](#concurrency-and-timeouts) below.

## Endpoints

### `GET /health`

```json
{"status": "ok", "database": "ok"}
```

### `POST /summaries` — start a run

Body (`SummaryCreate`):

```json
{
  "root_id": "00123",
  "question": "מה המצב?",
  "skill_keys": [],
  "boundaries": null
}
```

| Field | Required | Notes |
|---|---|---|
| `root_id` | one of `root_id`/`boundaries` | opaque string, ≤256 chars. **Never** send it as a number — `"00123"` must stay `"00123"`. |
| `question` | no | free text; empty is fine for an opening request |
| `skill_keys` | no | up to 3 keys from `GET /skills` |
| `boundaries` | one of `root_id`/`boundaries` | GeoJSON `MultiPolygon`, see below |

At least one of `root_id` / `boundaries` is required; you may send both. A
request with only `boundaries` runs every `agent_enabled` workflow whose
steps read `workflow.boundaries`; a step in some *other* selected workflow
that needs `workflow.id` degrades to a warning on that section rather than
failing the whole run.

**`boundaries` shape** (`GeoBoundaries`), RFC 7946, coordinates `[lng, lat]`:

```json
{
  "type": "MultiPolygon",
  "coordinates": [
    [
      [[34.75, 32.05], [34.80, 32.05], [34.80, 32.10], [34.75, 32.05]]
    ]
  ]
}
```

- `coordinates` is polygons → rings → points. Each ring needs ≥4 points and
  **must close** (`ring[0] == ring[-1]`, comparing lng/lat only).
- At least one polygon is required; a polygon needs at least one ring.
- The server converts this to an OGC `MULTIPOLYGON` WKT string before it
  reaches any package — you never construct WKT yourself.
- Only a workflow with a step whose `input_source` is `workflow.boundaries`
  will do anything with the area (set up in Agent Studio; see
  `FDE_GUIDE.md`). Sending boundaries against a deployment with no such
  workflow returns a completed run whose sections say there was nothing to
  run against the area — check that before assuming the script is broken.

Query parameter `wait` (0–300, default 0): seconds to block for the run to
finish before returning, instead of writing your own poll loop. `wait=0`
returns immediately with `status: "queued"`.

Response (`202` if still running, `200` if `wait` caught it finished):

```json
{
  "conversation": {"id": "conv_...", "root_id": "00123", "boundaries": null, "session_id": "..."},
  "run": {
    "id": "run_...",
    "conversation_id": "conv_...",
    "kind": "full",
    "status": "queued",
    "progress": {},
    "result": null,
    "error": "",
    "created_at": "...",
    "finished_at": null
  }
}
```

Sets the `aisummry_session` cookie — capture it here.

### `GET /runs/{run_id}` — poll a run

Same session-cookie rule as above. Returns the run row shown above, refreshed.

`status` lifecycle: `queued` → `running` → one of `completed` / `partial` /
`failed`. `partial` means at least one workflow section failed but every
successful section is still in the result — never treat `partial` as
"discard this".

While running, `progress` looks like:

```json
{"completed": 2, "total": 5, "sections": [ {"...": "section so far"} ]}
```

Once finished, `result` (`null` until then) is:

```json
{
  "headline": "one-line answer",
  "summary": "...",
  "coverage": "...",
  "key_findings": ["..."],
  "risks": ["..."],
  "missing_data": ["..."],
  "suggested_questions": ["..."],
  "skill_results": [
    {"skill_key": "...", "name": "...", "summary": "...", "items": ["..."], "sources": ["..."]}
  ],
  "sections": [
    {
      "workflow_id": "...", "workflow_key": "...", "name": "...",
      "status": "completed",
      "summary": "...", "coverage": "...",
      "facts": ["..."], "patterns": ["..."], "outliers": ["..."],
      "warnings": [], "suggested_questions": ["..."],
      "fields": {}, "degraded": false
    }
  ],
  "partial": false
}
```

On `status: "failed"`, `error` carries a message (Hebrew, user-facing) and
`result` stays `null`.

### `GET /runs/{run_id}/evidence`

The raw rows every step of every workflow in that run pulled, for auditing a
claim back to its source. Same session-cookie rule.

### `POST /conversations/{conversation_id}/messages` — follow-up

`FollowUpCreate`: `{"question": "...", "skill_keys": []}`. Reuses the
conversation's saved evidence/boundaries; not needed for a one-shot batch run
per area.

### `GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages`

History for the calling session. Also cookie-scoped.

### `GET /skills`

The Skills a user may attach via `skill_keys` (up to 3 per request):

```json
[{"content_key": "sandbox-exec-brief", "name": "תדריך מנהלים", "description": "..."}]
```

### FDE Studio routes

`packages`, `workflows`, `agent-content`, and `admin` under `/api` /
`/api/v1` configure tools, workflows, and Skills — that's Agent Studio's
surface, not what a run-the-agent script calls. See `backend/CLAUDE.md` and
`FDE_GUIDE.md` if you're scripting *setup* rather than *runs*.

## Errors

Every error is `{"detail": "<one Hebrew sentence>"}`:

| Status | Meaning |
|---|---|
| `422` | request validation failed (bad shape, e.g. an unclosed ring) |
| `404` | not found, **or** found but not yours (see the cookie section above) |
| `400` | other application error (`AppError` default) |
| `502` | the LLM/agent call failed (`AgentError`) |
| `500` | unhandled server exception; `detail` includes the exception type |

## Concurrency and timeouts

- The backend runs at most `max_parallel_workflows` full runs at once
  (default **4**: 3 workers for opening requests + 1 reserved for
  follow-ups) — everything past that queues server-side, so submitting more
  requests than that is fine, they just wait their turn. A single workflow
  step is bounded by `package_timeout_seconds` (default 120s) with one retry.
- **Recommended pattern for many areas**: submit every `POST /summaries`
  with `wait=0` (fast, doesn't hold a connection open), then poll
  `GET /runs/{id}` for each on an interval (1–2s) until it's finished. This
  is what `run_multipolygons.py` does. For a handful of areas, `wait=<N>`
  synchronous mode is simpler and fine too, just remember it blocks that
  connection for up to `N` seconds.
- Client-side concurrency should stay in the same ballpark as
  `max_parallel_workflows` — pushing far beyond it doesn't finish runs any
  faster, it just grows the server queue and holds more idle connections
  open.

## Minimal `curl` walkthrough

```bash
BASE=http://localhost:8000/api/v1

# 1. submit, keep the cookie
curl -sS -c cookies.txt -X POST "$BASE/summaries" \
  -H 'Content-Type: application/json' \
  -d '{"boundaries": {"type": "MultiPolygon", "coordinates": [[[[34.75,32.05],[34.80,32.05],[34.80,32.10],[34.75,32.05]]]]}}'
# -> {"conversation": {...}, "run": {"id": "run_abc", "status": "queued", ...}}

# 2. poll with the same cookie
curl -sS -b cookies.txt "$BASE/runs/run_abc"
```

## The script

`backend/scripts/run_multipolygons.py` reads a JSON list of areas (see
`backend/scripts/multipolygons.example.json`), submits each one, polls it to
completion with its own pinned session cookie, and writes one result file per
area plus a combined summary. It needs `httpx` (already a backend
dependency — `pip install httpx` if you're running it outside the backend's
own environment). Run it with:

```bash
cd backend
python3 scripts/run_multipolygons.py \
  --input scripts/multipolygons.example.json \
  --output-dir ./run_results
python3 scripts/run_multipolygons.py --help   # every option
```

Each `<output-dir>/<name>.json` holds `{name, ok, run_id, conversation_id,
status, headline, error, elapsed_seconds, run}` — `run` is the full run
object from `GET /runs/{id}` (see [above](#get-runsrun_id--poll-a-run)) for
when the headline alone isn't enough. `manifest.csv`/`manifest.json` roll up
every item's outcome for a quick pass/fail scan across the whole batch.
