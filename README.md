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
  timeline, cross-source contradictions, an entity map, an evidence-quality
  audit, a data profile, a distribution read, or an outlier scan. Each Skill
  runs in its own model call with its full instructions, and each result names
  the summary sections it used.
- The summary reads as one continuous answer — a headline, then prose that
  merges every workflow — rather than a card per workflow. The workflows it
  rests on appear as source chips underneath, and a chip opens that workflow's
  own raw evidence.

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

### Nginx reverse proxy

[nginx/nginx.conf](nginx/nginx.conf) puts the whole system behind a single
port: `/api/` goes to `backend:8000` and everything else to `frontend:3000`.
Add it to `docker-compose.yml` as a fourth service:

```yaml
  nginx:
    image: nginx:1.27-alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "80:80"
    depends_on:
      - backend
      - frontend
```

The whole app is then on http://localhost, and the `3000`/`8000` port mappings
on the other services become optional — drop them to expose only the proxy.

Two settings in that config are load-bearing:

- `proxy_buffering off` on `/api/` — summaries render progressively, and
  buffering would withhold the response until the run finished.
- 300s read/send timeouts — a package run is bounded backend-side by
  `run_bounded` (120s default, per-package overrides) and the provider retries
  once, so a shorter proxy timeout would cut off a run that is still valid.

### Exporting the images as a tar

For transfer into an air-gapped environment:

```bash
docker compose build
docker compose images          # confirm the generated image names first
docker save -o aisummryio-full.tar \
  aisummryio-backend aisummryio-frontend nginx:1.27-alpine postgres:16
```

Load it on the target host with `docker load -i aisummryio-full.tar`.

Compose prefixes image names with the project directory, so check
`docker compose images` rather than assuming the names above. The archive runs
roughly 1.5–2.5 GB, which is over GitHub's 100 MB per-file limit — keep it out
of git and move it out of band. Confirm no FLAPI credentials from `.env` were
captured into a layer before the file leaves the build machine.

### Backend image on its own

Compose runs its own throwaway PostgreSQL. To point the backend at a different
database, build and run the image directly. This follows the same pattern as
LocatoAI:

```bash
cd backend
docker build --platform linux/amd64 -t aisummryio-backend:latest .
```

Build for `linux/amd64` on Apple Silicon: Python 3.8 has no arm64 wheels for
part of the dependency set, and it matches the deployment target. Rebuild after
any code or dependency change.

**Against the shared server:**

```bash
docker run -d --name aisummry-backend --platform linux/amd64 -p 8000:8000 \
  -e AISUMMRY_DATABASE_URL='postgresql://spear:spear@rnd619-nv-prd01:5432/spear' \
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
  -v "$PWD/runtime-settings.json:/srv/backend/runtime-settings.json" \
  aisummryio-backend:latest
```

**Against PostgreSQL on the host machine:**

```bash
docker run -d --name aisummry-backend --platform linux/amd64 -p 8000:8000 \
  --add-host=pghost:host-gateway \
  -e AISUMMRY_DATABASE_URL="postgresql://$(whoami)@pghost:5432/summaries" \
  -v "$PWD/runtime-settings.json:/srv/backend/runtime-settings.json" \
  aisummryio-backend:latest
```

`pghost` is mapped to the host gateway by `--add-host`. Use it rather than
`host.docker.internal`, which resolves to an unreachable IPv6 address, and
never `localhost`, which is the container's own loopback — both fail as
`network is unreachable` on `::1`. The URL also needs an explicit user, since
the container user is not the host user.

Managing the container and running tests:

```bash
docker logs -f aisummry-backend
docker stop aisummry-backend && docker rm aisummry-backend

docker run --rm --platform linux/amd64 aisummryio-backend:latest python -m pytest -q
```

Add `-v "$PWD/app:/srv/backend/app"` to the run command to iterate on source
without rebuilding.

### Settings precedence

`runtime-settings.json` holds UI-saved settings and **overrides environment
variables**, so a stale file silently defeats an `-e` change. It is mounted
above so settings and the hashed admin password survive container restarts.
When mounted, its `database_url` must use `pghost` — not `localhost` — for a
host database.

`backend/.dockerignore` excludes the file, so an unmounted container starts
from environment variables alone.

The URL carries host, port, user, password, and database in one value; the
schema is separate. A password containing `@`, `:`, `/`, or `#` must be
percent-encoded.

### Frontend image

```bash
cd frontend
docker build -t aisummryio-frontend:latest .

docker run --rm -p 3000:3000 \
  --add-host=apihost:host-gateway \
  -e BACKEND_URL=http://apihost:8000 \
  aisummryio-frontend:latest
```

The same hostname rule applies: reach the backend through a `--add-host` alias,
not `localhost` or `host.docker.internal`.

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
  -e AISUMMRY_DATABASE_SCHEMA=mosaic_magen \
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
AISUMMRY_DATABASE_SCHEMA=mosaic_magen
```

Settings saved in the UI are written to `backend/runtime-settings.json` and
are applied **on top of** `.env`, so a stale file silently overrides an
environment change. Edit that file, or clear the field in the Settings screen,
when an environment change appears to have no effect.

Backend and frontend implementation rules are documented in their respective
`CLAUDE.md` files.

## Batch a spreadsheet of areas

`backend/scripts/area_batch.py` asks the same questions about every area in an
Excel sheet and writes the answers back into the same rows. One row holds one
area, as WKT (`MULTIPOLYGON`/`POLYGON`) or as GeoJSON.

```bash
cd backend
pip install openpyxl
python scripts/area_batch.py --workbook areas.xlsx --dry-run   # check the areas
python scripts/area_batch.py --workbook areas.xlsx
```

The questions, the column holding the area, which answer field lands in which
column, and the cooldown between calls (2 minutes by default) are the `CONFIG`
block at the top of the script; `--help` lists the per-run overrides. Runs are
sequential against a running service through `/api/v1`, the workbook is saved
after every row, and re-running asks only what is still unanswered — so an
interrupted batch resumes instead of repeating. See
[backend/scripts/CLAUDE.md](backend/scripts/CLAUDE.md).

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
6. Publish the workflow. The server blocks workflows without valid mappings or
   publishable examples.

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
