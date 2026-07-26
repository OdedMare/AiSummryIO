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
Settings screen. Backend and frontend implementation rules are documented in
their respective `CLAUDE.md` files.

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
