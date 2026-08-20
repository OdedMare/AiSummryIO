# AiSummryIO

Hebrew-first agent application for evidence-backed summaries by identifier.
FDEs configure versioned FLAPI packages, workflows, skills, prompts, and
examples; users provide one identifier and receive a progressive full summary.

## What it does

- The first request runs every agent-enabled `baseline`/`both` workflow.
- Follow-up questions reuse saved evidence and run a relevant `detail` workflow
  or one FDE-approved standalone tool only when more data is needed.
- An FDE can describe a goal in plain language; the planner builds a reviewable
  workflow draft from existing tools or specifies the missing tool contract.
- Each browser session can keep project workspaces: a named mission plus the
  exact tools, workflows, Skills, and specialist agents assigned to it. A
  project can be curated manually or use the FDE interview to author and attach
  a mission-specific Skill after explicit confirmation.
- Project selection is the application entry screen. Existing installations
  receive one protected `Hunger Games` workspace containing their current
  catalog; old conversations are attached to it without rewriting evidence.
- Workflows chain version-pinned FLAPI Flow Packages through `flunks`.
- Identifiers are opaque strings, including numeric-looking values such as
  `00123`; they are never converted to integers.
- Successful sections remain visible when another package fails, and raw
  evidence is available separately from the Hebrew summary.
- Users can add up to three enabled summary Skills to a run. The built-in
  Skills produce an executive brief, risk review, recommended actions, a
  timeline, cross-source contradictions, an entity map, an evidence-quality
  audit, a data profile, a distribution read, or an outlier scan. Each Skill
  runs in its own model call with its full instructions, and each result names
  the summary sections it used.
- The summary reads as one continuous answer — a headline, then prose that
  merges every workflow — rather than a card per workflow. The workflows it
  rests on appear as source chips underneath, and a chip opens that workflow's
  own raw evidence.
- A conversation is a thread. Follow-ups are resolved against the previous
  turns first, so a question naming its subject only by reference still routes,
  and the whole exchange renders as a transcript rather than a single answer
  that gets replaced.

There are no GIS providers or map dependencies.

## Specialist agents (agent mode)

Beyond running workflows directly, agent-enabled **specialists** can be
orchestrated as a bounded leader/worker team. A leader model picks the
relevant specialists and gives each a focused task; each worker selects only
the workflows and Skills assigned to it, and answers only from evidence that
belongs to it. The leader then reviews the collected sections and may ask up
to `agent_max_rounds` follow-up questions before synthesis.

The bounds are deliberate — agentic means selective, not unlimited:

- at most 2 specialists per question and 3 workflows overall;
- `agent_max_rounds` is clamped to 0–5, and **0 keeps the existing
  non-agent summary path** unchanged;
- a leader routing failure falls back to a single specialist rather than
  fanning out to all of them.

The run's progress carries an `agent_trace`, which the UI renders as live
agent activity (`AgentStatus`) and an inspectable trace (`AgentTrace`).

## Backend deployment: Docker and OpenShift

The root [Dockerfile](Dockerfile) builds the backend only. PostgreSQL, FLAPI,
and the OpenAI-compatible model endpoint stay external:

```bash
docker build --platform linux/amd64 -t aisummryio-backend:latest .
docker run --rm -p 8000:8000 \
  -e AISUMMRY_DATABASE_URL='postgresql://user:pass@db:5432/summaries' \
  -e AISUMMRY_DATABASE_SCHEMA=sumorai \
  -e AISUMMRY_LLM_BASE_URL='http://llm-gateway:11434/v1' \
  -e AISUMMRY_LLM_MODEL='gemma4:31b-cloud' \
  -e AISUMMRY_LLM_DIET_MODE=false \
  -e OPENAI_API_KEY='replace-if-required' \
  -e AISUMMRY_FLAPI_USERNAME='replace' \
  -e AISUMMRY_FLAPI_TOKEN='replace' \
  aisummryio-backend:latest
```

Build from the repository root. The internal `flunks` package must be
available from the Python package index visible during the build. On Apple
Silicon, keep `--platform linux/amd64`: Python 3.8 has no ARM wheel for part of
this dependency set.

### OpenShift

Push the same image to the registry available to the cluster, then create one
application from it:

```bash
docker tag aisummryio-backend:latest \
  <registry>/<project>/aisummryio-backend:latest
docker push <registry>/<project>/aisummryio-backend:latest

oc new-app --name aisummryio-backend \
  --image=<registry>/<project>/aisummryio-backend:latest
oc set env deployment/aisummryio-backend --from=secret/aisummryio-backend
oc expose service/aisummryio-backend
oc logs -f deployment/aisummryio-backend
```

Create `secret/aisummryio-backend` through the organization's secret manager
with these keys:

- `AISUMMRY_DATABASE_URL`, `AISUMMRY_FLAPI_TOKEN`, and optionally
  `AISUMMRY_DATABASE_PASSWORD`;
- `OPENAI_API_KEY` exactly as written — not `AISUMMRY_OPENAI_API_KEY`;
- `AISUMMRY_ADMIN_PASSWORD` and `AISUMMRY_COOKIE_SECRET`.

Set the non-secret values on the Deployment: `AISUMMRY_DATABASE_SCHEMA`,
`AISUMMRY_LLM_BASE_URL`, `AISUMMRY_LLM_MODEL`,
`AISUMMRY_LLM_DIET_MODE=false`, and `AISUMMRY_FLAPI_USERNAME`. The model URL
must be reachable from the pod; `localhost` means the backend container itself.
The image listens on port 8000 and supports OpenShift's arbitrary non-root UID.

`/data/runtime-settings.json` stores settings saved from the UI and overrides
environment variables. Mount `/data` only if those UI changes should survive a
pod replacement. If a PVC already contains this file, check it first when an
environment change seems ignored.

### Why plan-chat can work while summaries do not

Both paths use the same model client. A new database, however, has no active
summary workflow: the seeded example is intentionally disabled. `/summaries`
calls the model only after at least one enabled workflow with role `baseline`
or `both` collects evidence. Create such a workflow in Agent Studio and verify
its dry run before testing the summary route.

If a workflow is active but the model rejects a section or final-summary call,
the result now has `degraded: true`, includes the model error under warnings or
`missing_data`, and logs `section synthesis degraded` or
`final synthesis degraded`. Start with:

```bash
oc logs deployment/aisummryio-backend | grep -E \
  'summary skipped|synthesis degraded|FAILED run'
```

Compose and the Helm charts remain available for local or existing installs,
but they are not part of this OpenShift path. The frontend remains a separate
image built from `frontend/`.

## Frontend deployment

The frontend serves the app and proxies `/api/*` to the backend itself, so the
browser stays same-origin and no reverse proxy sits in front of it:

```bash
docker build -t aisummryio-frontend:latest ./frontend
docker run --rm -p 3000:3000 \
  -e BACKEND_URL='http://aisummryio-backend:8000' \
  aisummryio-frontend:latest
```

`next build` compiles the `/api/*` rewrite target into the build output, so
`BACKEND_URL` cannot take effect as a plain runtime variable. The image is
built against an unresolvable sentinel host, and
[`frontend/docker-entrypoint.sh`](frontend/docker-entrypoint.sh) substitutes
the real value into the recorded build artifacts on every container start,
regenerating them from pristine copies so a restart with a changed
`BACKEND_URL` takes effect. One image therefore runs against any backend —
Compose, the sandbox, and the Helm chart all pass it as an ordinary
environment variable, and changing it needs a restart, not a rebuild.

`BACKEND_URL` must be reachable **from the frontend container**: a Compose
service name, or a cluster-internal Service, never a public host. It defaults
to `http://127.0.0.1:8000`, which inside a container means the frontend
itself, so leaving it unset only works when the backend shares that network
namespace. The container start logs the target it resolved.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every branch push
and pull request:

- **Build backend image** — then `import app.main` inside it, proving the image
  starts rather than merely layering.
- **Build frontend image** — `npm run build` runs in the Dockerfile, so a type
  error or failed Next build fails the job. The built image is then started
  with a `BACKEND_URL` of its own, proving the entrypoint really rewrites the
  compiled proxy target instead of shipping the build-time sentinel.
- **Lint charts** — `helm lint` plus `helm template` against
  `ci/test-values.yaml` (rendering the real credentialed paths, not empty
  defaults), and the missing-database guard above.

Neither image is pushed. In-flight runs for a branch are cancelled when a new
commit lands.

## Operations

- `GET /api/health` reports database status, `worker_capacity`, and
  `abandoned_workers` — threads lost to FLAPI timeouts.
- `GET /api/health/live` is a separate **liveness** probe that fails only once
  abandoned threads have eaten the whole pool. A `tcpSocket` probe stays green
  in exactly that state: the port is open, the process is fine, and no run will
  ever start again. That is the one condition a pod restart actually fixes,
  which is why it is not folded into `/api/health` — that endpoint must keep
  reporting for a human even when the answer is bad.
- A watchdog in `JobRunner` reports in-flight runs every 15s and calls out any
  past 180s, since a hang inside `flunks` emits nothing at all. It also purges
  expired conversations every 5 minutes.
- Logging is configured in `common/logging_setup.py` before any other logger is
  constructed, so no start-up line is lost. Unhandled exceptions are logged with
  a full traceback and returned as JSON — Starlette otherwise returns a bare
  non-JSON "Internal Server Error". The 1.5s run poll is traced at DEBUG so it
  cannot bury everything else; the browser console follows the same rule in
  `services/api.ts`.
- Idle conversations expire after `conversation_idle_minutes` (60 default) and
  are cleaned up automatically; conversations, tools, and workflows can also be
  deleted explicitly. Deleting a workflow or tool keeps past evidence, so an
  existing summary stays traceable.

### Connection notes

`rnd619-nv-prd01` is an internal hostname. It resolves only on the corporate
network or VPN — off it, DNS returns `NXDOMAIN` and the backend cannot start a
run. Verify before launching:

```bash
nslookup rnd619-nv-prd01
```

If the host resolves on the machine but not inside the container, which some
VPN clients cause, pin the address the same way:

```bash
docker run -d --name aisummry-backend --platform linux/amd64 -p 8000:8000 \
  --add-host rnd619-nv-prd01:<ip-address> \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=sumorai \
  aisummryio-backend:latest
```

The backend Dockerfile copies the source before `pip install`, so any source
edit reinstalls every dependency. Backend rebuilds are slow by design.

## Local development

The source versions match LocatoAI: Python 3.8.10, Next.js 16.2.10,
React 18.3.1, and TypeScript.

```bash
cd backend
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

```bash
cd frontend
npm ci
npm run dev
```

Start PostgreSQL first and configure values through `backend/.env` or the FDE
Settings screen. For the shared database:

```bash
AISUMMRY_DATABASE_URL=postgresql://spear:spear@rnd619-nv-prd01:5432/spear
AISUMMRY_DATABASE_SCHEMA=sumorai
```

Settings saved in the UI are written to `backend/runtime-settings.json` and
are applied **on top of** `.env`, so a stale file silently overrides an
environment change. Edit that file, or clear the field in the Settings screen,
when an environment change appears to have no effect.

Backend and frontend implementation rules are documented in their respective
`CLAUDE.md` files.

## First FDE setup

Step-by-step instructions, exact field meanings, a troubleshooting table, and
a new-environment checklist are in **[FDE_GUIDE.md](FDE_GUIDE.md)**. The short
version:

1. Sign in to **Agent Studio**.
2. Add each FLAPI package as a tool, including when the agent may use it,
   example string input, and example output rows.
3. Use **Fetch 1 ID** with a safe identifier to preview one tool run and infer
   its output schema. It also fills empty examples, asks the model for editable
   Hebrew metadata suggestions, and exposes draggable fields that the FDE can
   include in or exclude from summarization; review everything before saving.
4. Ask the planner for a draft or build one from tool steps, then map later
   inputs from earlier output fields.
5. Run a live dry-run with a safe identifier.
6. Choose the responsible specialist and save the workflow. It is assigned to
   that specialist in the same save and is live as soon as it is saved; the
   server refuses invalid step mappings, and "פעיל לסוכן" is what holds a
   workflow back while it is still being built. Once specialists exist, an
   active workflow cannot be saved without choosing one.

The agent is also reachable **per field**: every prose field on the tool and
workflow forms carries its own small agent button, which opens the interview
beside that field and writes back only that field. On the workflow editor the
route itself (`steps`) is one of those focuses — accepting it loads the whole
step array onto the canvas without touching the name and description already
written. Interview questions may offer two to four clickable answers, the first
being the agent's own recommendation; typing a different answer is always
available.

The studio is preloaded with ten user-facing summary Skills and separate
operator guidance for building, testing, and diagnosing workflows. A manager
can add more Skills and choose which ones appear on the summary screen.

Skill instructions are written in English — models follow English guidance more
precisely — and each one directs the model to read the Hebrew sections and
return Hebrew. The seeded Skills are also the template to copy: each states
what it produces, its method, its evidence rules, its format, and a worked
example.

**Test a Skill without a full run.** The Skill editor has a
`בדיקת ה-Skill` panel that runs only the Skill against sample sections, so
wording can be iterated in seconds without executing packages or persisting
anything. It also lists sources the Skill cited that do not exist — the
citations the evidence rule silently drops in a real run.
