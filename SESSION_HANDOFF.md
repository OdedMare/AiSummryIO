# AiSummryIO — session handoff

Use this document as the source of truth when continuing the project in a new
Codex session.

## Start the next session with this instruction

> Continue AiSummryIO from `SESSION_HANDOFF.md`. First read `README.md`,
> `backend/CLAUDE.md`, and `frontend/CLAUDE.md`. Inspect the current code and
> Git status before changing anything. Preserve the locked product decisions
> below, use Ponytail/simple implementation style, and do not rebuild completed
> work. Begin with the first unfinished P0 item, implement it, test it, and
> continue toward a fully deployable production app.

## Repository state

- Main working copy:
  `/Users/odedmarellie/Desktop/repos/AiSummryIO`
- Verified clean clone:
  `/Users/odedmarellie/Desktop/repos/AiSummryIO-clean-clone`
- GitHub: `https://github.com/OdedMare/AiSummryIO`
- Branch: `main`
- LocatoAI reference:
  `/Users/odedmarellie/Desktop/repos/locatoAi`
- LocatoAI source branch and commit:
  `agiles_changes` at `a31edfe8aabc7801aea1f8b1eaa0bcb5629000c8`
- Do not modify the LocatoAI repository.

At the end of the previous session, the working copy and `origin/main` matched.
Always confirm this again with:

```bash
git status --short
git log -5 --oneline --decorate
```

## Locked product decisions

- This is a real application, not an MVP or mock.
- Hebrew is the primary language and the UI is RTL.
- The app summarizes everything available about one opaque string identifier.
- Numeric-looking IDs such as `00123` must remain strings.
- The initial request runs every published `baseline`/`both` workflow.
- Follow-up questions reuse stored evidence first and run relevant detail
  workflows only when more data is required.
- Use FLAPI Flow Packages through the internal `flunks` library only.
- Do not add GIS providers, MQS, Tyche, Cubes execution, or a map.
- Workflows may chain package output into later package input and support
  one-to-many fan-out.
- Independent workflows run concurrently; package failures retry once and must
  produce visible partial results without deleting successful sections.
- Every factual claim must ultimately be traceable to workflow, step, and raw
  evidence.
- FDEs manage packages, workflows, skills, prompts, examples, tests, publishing,
  and review through Agent Studio.
- Regular users are anonymous. FDE and Settings access share one password.
- Never commit or log that password. Store only a salted hash or receive it
  through `AISUMMRY_ADMIN_PASSWORD`.
- PostgreSQL, live runtime settings, and the OpenAI-compatible client follow the
  LocatoAI patterns.
- Keep dependencies and implementation simple. Prefer existing LocatoAI
  patterns and standard-library behavior over new abstractions.

## Work completed in the previous sessions

### Backend

- FastAPI API with persistent PostgreSQL conversations, runs, progress,
  evidence, feedback, packages, workflows, skills, prompts, and settings.
- LocatoAI-style live settings store with masked secrets.
- Salted `scrypt` FDE password hashing and signed HttpOnly cookies.
- LocatoAI-compatible OpenAI JSON client with response-format degradation and
  retry behavior.
- FLAPI provider and mapper through `flunks`.
- `PackageInputCube.values` receives string identifiers without integer
  conversion.
- Generic package output rows are preserved even when no geometry exists.
- Package retry-once behavior and package query provenance.
- Versioned package catalog, workflow drafts/publishing, agent content, and
  seeded Hebrew skills/prompts.
- Baseline and detail workflow roles.
- Sequential package chaining and string-ID fan-out.
- Parallel independent workflows.
- Progressive persisted run state and separate evidence endpoint.
- Follow-up router that can use cached evidence, select a detail workflow, or
  ask for clarification.
- Dedicated higher-priority executor for follow-up runs.
- Startup recovery for queued jobs and cleanup of expired conversations.
- Publish validation for step ordering/mappings and required examples.
- Runtime cookie secret and local password hash persistence.
- Docker permissions for the runtime settings volume and logs.

### Frontend

- Next.js/React/TypeScript Hebrew RTL application.
- LocatoAI-style dark navigation/history shell with no map.
- Identifier field, optional identifier extraction from a message, and explicit
  confirmation before starting.
- Progressive workflow sections, status/progress, partial failures, feedback,
  and raw evidence drawer.
- Settings panel with FDE authentication, live model/settings controls, FLAPI,
  PostgreSQL, concurrency, timeout, and retention fields.
- Agent Studio with:
  - package catalog and version creation;
  - single/many string input modes;
  - package input/output examples;
  - structured workflow step editor;
  - package-output-to-input mappings;
  - dependency preview;
  - baseline/detail/both roles;
  - live dry-run;
  - workflow publishing;
  - skill and prompt editing/publishing;
  - review queue.
- Responsive light/dark design, visible focus states, reduced-motion support,
  Lucide icons, accessible labels, and 44px interaction targets.

### Project and documentation

- Python runtime pinned to 3.8.10.
- Frontend matches LocatoAI's Next.js 16.2.10, React 18.3.1, and TypeScript
  baseline, with GIS dependencies removed.
- `backend/CLAUDE.md` and `frontend/CLAUDE.md` were added.
- Docker Compose includes PostgreSQL, backend, and frontend.
- Docker ignore files prevent large build contexts.
- Root README documents setup and the first FDE workflow.
- A persisted UI design system exists at
  `design-system/aisummryio/MASTER.md`.
- GitHub repository was created/synchronized and a separate clean clone was
  verified.

## Validation already completed

- Backend unit tests: `6 passed`.
- Manual live PostgreSQL integration covered:
  - schema creation;
  - seeded skills/prompts;
  - FDE login;
  - package creation;
  - workflow draft and publish;
  - background summary execution;
  - partial failure behavior;
  - evidence retrieval.
- All backend files parse under the exact Python 3.8.10 container.
- Frontend ESLint passed.
- TypeScript `--noEmit` passed.
- Next.js production build passed.
- Frontend Docker image built and served an HTTP 200 page.
- Both Dockerfiles passed `docker build --check`.
- Docker Compose configuration validation passed.
- The clean GitHub clone independently passed backend tests, frontend lint,
  TypeScript, production build, and Compose validation.

Visual screenshot QA could not be completed because no controllable browser was
available in that session. Do it in a future session when Browser/Chrome is
available.

## Remaining work before calling the app fully production-ready

Work in this order. Do not mark an item complete without an automated or
repeatable verification.

### P0 — real environment and end-to-end summary

- [ ] Make the internal `flunks` wheel/index available to the backend Docker
  build and pin the exact tested version/checksum.
- [ ] Verify that the air-gapped `flunks` build accepts arbitrary string values
  in `PackageInputCube.values`; patch that internal library if its model still
  restricts identifiers.
- [ ] Configure a real PostgreSQL database, FLAPI credentials, OpenAI-compatible
  endpoint/key/model, and the agreed FDE password through deployment secrets.
- [ ] Add real package catalog entries and representative string-ID examples.
- [ ] Create and publish the first real baseline and detail workflows.
- [ ] Run a real identifier through the entire Docker stack and verify package
  calls, evidence rows, Hebrew section summaries, final summary, and follow-up
  behavior.
- [ ] Decide whether to keep LocatoAI's exact vulnerable Next.js `16.2.10` pin
  or move both projects to a patched release. The last audit reported 12 high
  advisories in the full dependency tree and 3 in the production image; npm
  identified `16.2.12` as the patch at that time.

### P1 — workflow correctness and FDE publishing

- [ ] Execute saved examples as real offline regression tests instead of merely
  checking that examples exist.
- [ ] Persist test results and block publishing when mandatory examples fail.
- [ ] Validate and use each workflow's `output_schema`; the current runtime
  stores it but summarizes with the shared section schema.
- [ ] Add package connection/config validation and a safe test-package action.
- [ ] Expose and use per-package timeout settings. The setting exists but is
  not yet enforced around a `flunks` run.
- [ ] Pass `flapi_verify_tls` into the actual FLAPI client configuration; it is
  currently stored but not consumed.
- [ ] Validate that `depends_on` matches each step's input source; execution is
  currently ordered but does not use a complete dependency scheduler.
- [ ] Add version history, diff, rollback, and audit records for packages,
  workflows, skills, and prompts. Older rows exist, but the current UI lists
  only the latest version.
- [ ] Bind versioned skills/prompts/examples to workflow versions. Skills are
  currently editable content, but they are not pinned or executed by a
  workflow.
- [ ] Add approval state for few-shot examples and keep regression-only
  examples out of runtime prompts.

### P1 — production job and data reliability

- [ ] Replace the in-process-only job executors with PostgreSQL job claiming
  and leases (`FOR UPDATE SKIP LOCKED`) or an approved persistent worker queue.
  Multiple backend replicas must not execute the same run.
- [ ] Add idempotency keys, retry classification, attempt records, cancellation,
  and stale-job recovery.
- [ ] Add proper schema migrations rather than running the complete schema
  string at application startup.
- [ ] Add a PostgreSQL connection pool and production transaction boundaries.
- [ ] Enforce bounded raw output size, row limits, evidence pagination, and
  chunk persistence so very large package responses do not live in one JSONB
  value or one browser `<pre>`.
- [ ] Run retention cleanup on a schedule. `log_retention_days` is configurable
  but operational log rotation/deletion is not implemented.
- [ ] Add database backup/restore documentation and test a restore.

### P2 — complete user experience

- [ ] Render the full conversation transcript. The current workspace shows only
  the latest run and replaces the previous summary on follow-up.
- [ ] Render every agreed final-summary area: identity/core data, workflow
  findings, related entities, risks, missing/failed data, evidence, and
  suggested follow-ups.
- [ ] Make suggested follow-up questions clickable.
- [ ] Support multi-workflow follow-up plans when a question requires several
  detail workflows; the current router selects at most one.
- [ ] Include relevant conversation history when routing ambiguous follow-ups
  and continuing after a clarification question.
- [ ] Attach evidence references to individual claims/facts, not only to an
  entire workflow section.
- [ ] Add paginated/filterable evidence inspection and export.
- [ ] Add written feedback comments and a complete FDE review lifecycle:
  assignment, status, notes, resolution, and links to the affected run.
- [ ] Replace raw JSON example/schema fields with understandable structured
  editors and show readable dry-run/regression differences.
- [ ] Improve the dependency preview so branches and fan-out are represented
  accurately rather than as a linear row.
- [ ] Add unsaved-change protection and draft autosave in Agent Studio.
- [ ] Add modal focus trapping, Escape handling, focus restoration, skip link,
  and automated accessibility checks.
- [ ] Perform screenshot and interaction QA at desktop, 375px mobile, and
  landscape in both themes and with reduced motion.

### P2 — security and operations

- [ ] Set production cookie flags (`Secure`, domain/path policy, configurable
  lifetime) and add CSRF protection for authenticated mutations.
- [ ] Add rate limits and body-size limits for login, summary, feedback, and
  Studio endpoints.
- [ ] Move database/FLAPI/LLM secrets to the deployment secret manager. The
  runtime JSON must not become the production source for plaintext service
  credentials.
- [ ] Sanitize provider and database errors before displaying them to users.
- [ ] Add request/run correlation IDs, structured logs, metrics, traces, token
  usage, package duration, retry counts, and partial-success metrics.
- [ ] Add readiness/liveness checks, Docker health checks, restart policies,
  resource limits, TLS/reverse-proxy configuration, and production deployment
  documentation.
- [ ] Decide on a supported Python upgrade plan: Python 3.8.10 matches LocatoAI
  but is end-of-life.

### P2 — automated delivery

- [ ] Commit repeatable PostgreSQL API integration tests; the previous
  integration verification was run manually.
- [ ] Add workflow-engine tests for multiple workflows, fan-out, partial
  failures, routing, clarification, job recovery, and evidence ownership.
- [ ] Add frontend component tests and browser end-to-end tests for the user
  flow, Settings, and Agent Studio.
- [ ] Add a FLAPI contract test using the exact internal `flunks` wheel.
- [ ] Add GitHub Actions or the air-gapped CI equivalent for Python 3.8 tests,
  lint/typecheck/build, dependency scanning, Docker builds, and integration
  tests.

## Commands for the next session

```bash
cd /Users/odedmarellie/Desktop/repos/AiSummryIO/backend
PYTHONPATH=. python -m pytest -q
```

```bash
cd /Users/odedmarellie/Desktop/repos/AiSummryIO/frontend
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

```bash
cd /Users/odedmarellie/Desktop/repos/AiSummryIO
AISUMMRY_ADMIN_PASSWORD='<deployment secret>' docker compose config --quiet
```

Do not put the real password or service credentials into commands that will be
committed, logs, screenshots, test fixtures, or this document.

## Local-only state

- The main working copy has an ignored `backend/runtime-settings.json`
  containing a salted FDE password hash and cookie secret. It is intentionally
  absent from Git and from clean clones.
- `graphify-out/` is ignored. A graph audit was started and then intentionally
  interrupted when the user requested this handoff instead. Treat its partial
  files as disposable; rebuild the graph before relying on it.
