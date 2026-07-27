# AiSummryIO

Hebrew-first agent application for evidence-backed summaries by identifier.
FDEs configure versioned FLAPI packages, workflows, skills, prompts, and
examples; users provide one identifier and receive a progressive full summary.

## What it does

- The first request runs every published `baseline`/`both` workflow.
- Follow-up questions reuse saved evidence and run a relevant `detail` workflow
  or one FDE-approved standalone tool only when more data is needed.
- An FDE can describe a goal in plain language; the planner builds a reviewable
  workflow draft from existing tools or specifies the missing tool contract.
- Workflows chain version-pinned FLAPI Flow Packages through `flunks`.
- Identifiers are opaque strings, including numeric-looking values such as
  `00123`; they are never converted to integers.
- Successful sections remain visible when another package fails, and raw
  evidence is available separately from the Hebrew summary.
- Users can add up to three published summary Skills to a run. The built-in
  Skills produce an executive brief, risk review, recommended actions, a
  timeline, cross-source contradictions, an entity map, or an evidence-quality
  audit. Each Skill runs in its own model call with its full instructions, and
  each result names the summary sections it used.

There are no GIS providers or map dependencies.

## Run with Docker

### Full stack (Compose)

Builds the backend and frontend images and starts them with a local
PostgreSQL container:

```bash
export AISUMMRY_ADMIN_PASSWORD='your-fde-password'
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

The password is hashed on first start and persisted in the settings volume; it
is never committed. In an air-gapped environment, make the internal `flunks`
package available through the network's Python package source before building.

Everyday Compose commands:

```bash
docker compose up --build -d          # rebuild and run detached
docker compose up --build -d backend  # rebuild one service only
docker compose logs -f backend        # tail a service
docker compose ps                     # what is running
docker compose down                   # stop, keep the data volumes
docker compose down -v                # stop and DELETE the database volume
```

`down -v` destroys the `summaries-db` volume and every conversation, workflow,
and piece of evidence in it. Use plain `down` unless a clean database is the
goal.

### Backend image against the shared database

Compose runs its own throwaway PostgreSQL. To point the backend at the shared
server instead, build and run the image directly:

```bash
docker build -t aisummryio-backend:latest ./backend

docker run --rm -p 8000:8000 \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
  -e AISUMMRY_ADMIN_PASSWORD='your-fde-password' \
  aisummryio-backend:latest
```

The URL carries host, port, user, password, and database in one value; the
schema is separate. A password containing `@`, `:`, `/`, or `#` must be
percent-encoded in the URL.

`backend/.dockerignore` excludes `runtime-settings.json` and `.env`, so a
container never inherits local settings — it starts from these variables
alone. To keep settings and the hashed password across restarts, mount a
volume:

```bash
docker run --rm -p 8000:8000 \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
  -e AISUMMRY_RUNTIME_SETTINGS_FILE=/data/runtime-settings.json \
  -v aisummry-settings:/data \
  aisummryio-backend:latest
```

Detached, with logs:

```bash
docker run -d --name aisummry-backend -p 8000:8000 \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
  aisummryio-backend:latest

docker logs -f aisummry-backend
docker stop aisummry-backend && docker rm aisummry-backend
```

The frontend image builds the same way and needs the backend's address:

```bash
docker build -t aisummryio-frontend:latest ./frontend

docker run --rm -p 3000:3000 \
  -e BACKEND_URL=http://host.docker.internal:8000 \
  aisummryio-frontend:latest
```

### Connection notes

`rnd619-nv-prd01` is an internal hostname. It resolves only on the corporate
network or VPN — off it, DNS returns `NXDOMAIN` and the backend cannot start a
run. Verify before launching:

```bash
nslookup rnd619-nv-prd01
```

If the host resolves on the machine but not inside the container, which some
VPN clients cause, pin the address:

```bash
docker run --rm -p 8000:8000 \
  --add-host rnd619-nv-prd01:<ip-address> \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
  aisummryio-backend:latest
```

Never use `localhost` in a container's database URL. Inside the container it
resolves to the container's own loopback — `::1` first on most hosts — which
fails as `connection refused` or `network is unreachable`. Use the real
hostname, or `host.docker.internal` for a database running on the host.

Building on Apple Silicon for an x86 server needs an explicit platform:

```bash
docker build --platform linux/amd64 -t aisummryio-backend:latest ./backend
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
AISUMMRY_DATABASE_SCHEMA=mosaic_magen
```

Settings saved in the UI are written to `backend/runtime-settings.json` and
are applied **on top of** `.env`, so a stale file silently overrides an
environment change. Delete it to fall back to the environment.

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
   its output schema; review the schema before saving the tool version.
4. Ask the planner for a draft or build one from tool steps, then map later
   inputs from earlier output fields.
5. Run a live dry-run with a safe identifier.
6. Publish the workflow. The server blocks workflows without valid mappings or
   publishable examples.

The studio is preloaded with seven user-facing summary Skills and separate
operator guidance for building, testing, and diagnosing workflows. A manager
can publish more Skills and choose which ones appear on the summary screen.

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
