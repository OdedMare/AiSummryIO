# SumOrAI frontend context

Read this before changing `frontend/`.

## Product

Hebrew-first (`lang="he"`, `dir="rtl"`) workspace for complete summaries by
identifier. The UI reuses LocatoAI's shell: dark history/navigation rail,
bounded conversation, bottom composer, Settings, tool catalog, and Agent
Studio. It also has a small optional map picker in the composer
(`components/MapWorkspace/`), ported from LocatoAI: one or more drawn
polygons/rectangles scope the request, travelling as a single GeoJSON
`MultiPolygon`. It is a picker, not LocatoAI's full map workspace — no result
layers, no layer catalog, no plan pipeline.

## Commands

```bash
cd frontend
npm run dev
npm run build
npm run lint
npx tsc --noEmit
```

This is Next.js **16.2.10** with React **18.3.1**. When a Next API is
uncertain, inspect `node_modules/next/dist/docs/` instead of relying on older
training knowledge.

## Structure

The three large studio files were split by concern; each directory holds its
own model/hook plus the views over it. Reach for the smallest file that owns
the concern rather than growing the barrel component again.

```text
components/
├── AppShell/
│   ├── index.tsx            composition; useAppShell owns the state
│   ├── useAppShell.ts       conversation, question, history, panels
│   ├── useRunPolling.ts     the 1.5s poll, isolated from the shell
│   ├── useShellTheme.ts     theme persistence
│   └── commands.ts          composer command parsing (`/skill`, identifiers)
├── AgentStudioPanel/
│   ├── SpecialistStudio.tsx      create, edit, and enable specialists
│   ├── packages/                 packageModel.ts + usePackageCatalog.ts
│   │                             and PackageAgents/Fields/Schema views
│   ├── planning/                 usePlanChat.ts, PlanChatView, overlays
│   └── workflow/                 workflowModel.ts, canvasGraph.ts,
│                                 useWorkflowEditor/useWorkflowCanvas,
│                                 and the step/field/agent views
└── SummaryWorkspace/
    ├── Turn.tsx             one question+answer pair in the transcript
    ├── AgentStatus.tsx      live "what the agent is doing" line
    ├── AgentTrace.tsx       inspectable leader/worker trace
    └── NextQuestions.tsx    suggested-question chips
```

`styles/globals.css` is now only an import list. Styles live in `shell.css`,
`conversation.css`, `composer-map.css`, `settings.css`, `studio.css`, and
`planning.css` — add a rule to the file that owns the surface, not to
`globals.css`.

## State and API

`components/AppShell/index.tsx` composes the shell; `useAppShell.ts` owns the
active conversation, root string ID, question, history, theme, Settings, and
Agent Studio visibility, and `useRunPolling.ts` owns the poll on its own.
`services/api.ts` is the browser's only backend boundary.

Every backend call is traced to the console with the request body that caused
it — the Hebrew message the UI shows is deliberately short, and a 4xx/5xx is
only diagnosable next to what was actually sent. The run poll is exempt unless
it fails or exceeds 3s, for the same reason the backend traces it at DEBUG.

Evidence is paginated (`evidencePage(runId, evidenceId, offset, limit)`), so
the drawer must not assume it holds every row for a source.

An initial request posts `{root_id, question, skill_keys, boundaries}`, where
`boundaries` is a GeoJSON `MultiPolygon` or `null`. The API returns a
persistent run ID; poll it until complete while rendering progressive workflow
sections. Follow-ups post to the same conversation and retain the original
ID/evidence, and reuse the conversation's stored boundaries.

## UX rules

- Hebrew is primary; IDs, URLs, JSON, model names, and credentials stay LTR.
- Every input has a visible label and nearby validation.
- All icon buttons have an accessible name and at least a 44px target.
- Status changes use text/icons, not color alone; errors use `role="alert"`.
- Evidence is progressive disclosure: summary first, raw records on demand.
- **The workspace is a transcript, not a single answer.** `SummaryWorkspace`
  renders every run in the conversation through `Turn`; `runs` is the thread
  and `run` is only the turn still being polled. Showing just the latest run
  made a follow-up read as a replacement for the summary before it. Each turn
  renders the user's question above its answer — a transcript of answers alone
  forces the reader to remember what was asked — and turns are separated by a
  rule rather than a card, for the same reason the answer itself is not a card
  per workflow. Only the first turn keeps its `RunHeader`.
- Evidence is one drawer for the whole thread (`EvidenceView`, held by the
  workspace and keyed by run id), so opening a turn's sources closes another's
  instead of leaving drawers stacked down the page. Feedback stays per turn:
  a 1-5 star `radiogroup` (`TurnFooter` in `Turn.tsx`), not thumbs up/down —
  the backend averages it per route and feeds it to the follow-up router as a
  tie-breaking signal, so a graded rating carries more than a binary one did.
- The thread auto-scrolls on the turn count and the last turn's status only.
  Scrolling on every 1.5s poll would fight a user reading an earlier answer.
- **Progress reads as the agent talking, not as a job queue.** `AgentStatus`
  replaces the status pill, the percentage bar, and the "x מתוך y תהליכים"
  readout: it says what the agent is doing and names each source as it lands.
  `RunHeader` is now the thread title alone and `PendingAnswer` no longer
  carries its own spinner — two live indicators on one turn said the same
  thing twice. A finished turn shows no status: the answer is the status.
  "ממתין בתור" is deliberately not surfaced; the user asked a question and is
  owed an answer about it, not about our scheduler.
- **The agent trace is disclosure, not the answer.** When a run carries an
  `agent_trace`, `AgentStatus` names the phase in progress (delegating,
  questioning, synthesizing) and `AgentTrace` exposes which specialists were
  asked what, on demand. It stays collapsed by default: the user asked a
  question and is owed an answer, not our orchestration. `missing_data` the
  leader reported is surfaced with the answer, since a gap the agent knows
  about must not be silent.
- **`suggested_questions` renders as clickable chips** (`NextQuestions`) under
  the newest turn only — chips under an older answer invite reopening a
  question the thread has moved past. Clicking asks immediately through
  `app.ask`, which shares `send` with the composer's `submit` so a suggested
  question still passes identifier detection, `/skill` parsing, and the busy
  guard. These offer the user their next question; they never ask the user
  anything, and the composer stays the way to ask something else.
- **The map picker accumulates parts into one `MultiPolygon`.** `geometry` is
  a `GeoJSONPolygon[]`, and each finished shape is appended rather than
  replacing the last: a scope is often several disjoint areas, and redrawing
  from scratch to add one is the wrong cost. The draw tool therefore stays
  armed after a shape closes (leaflet-draw disarms itself, so `MapGeoms`
  re-enables it) and the mode is not reset on `onGeometryDrawn`. Removing a
  part is explicit — "ביטול אזור אחרון" drops the last one, "ניקוי הכל"
  empties the selection — since a click on the map adds and never deletes.
  `toMultiPolygonParts` returns `null` for an empty selection, because
  `GeoBoundaries` rejects an empty `coordinates` ("נדרש לפחות פוליגון אחד")
  while the API contract sends `boundaries: null` when nothing was drawn.
- **The drawn area is also the request's identifier.** A map request is sent
  with `root_id: null` and comes back with the conversation's `root_id` set to
  the area's `MULTIPOLYGON` WKT — the backend derives it, so the polygon has
  one serializer instead of one per side of the wire. `send` adopts what came
  back. Such an identifier is thousands of characters, so the topbar and the
  history rows show it through `identifierLabel` with the full value on
  `title`; they name a conversation and are not where the value is read.
- Conversation history is titled by the opening question; the raw identifier
  is secondary. Conversations created before titles fall back to the
  identifier.
- **The summary is one continuous answer, not a card per workflow.** `.answer-body`
  merges every section into flowing prose (headline, summary, findings, risks,
  gaps) at a capped measure, and `SourceRow` below it is where the section model
  survives — as provenance. A source chip opens that workflow's own evidence by
  filtering the drawer on its `evidence_ids`; "הצגת ראיות" clears the filter back
  to the whole run.
- Citations are **section-level, never per-claim**, because `_safe_section` in
  `synthesis.py` passes only `workflow_key/name/status/summary/facts/warnings` to
  the final-summary model — `evidence_ids` never reaches it, so the model cannot
  tag a claim with a source. Do not render per-claim citation chips off the
  current API; they would be guesses, and every claim must stay traceable.
- Section `warnings` and `degraded` lost their card, so they collect in
  `.answer-warnings` at the end of the answer. A partial source has to say so in
  the prose, not only as a dot on its chip.
- Before synthesis finishes `result` is null while sections stream in, so
  `PendingAnswer` renders the arrived section summaries as paragraphs. The answer
  assembles as sources land instead of staying blank and popping in whole.
- **The main chat never asks the user a question back.** A clarifying run
  still carries `recommendation` and `options` from the router, and the UI
  deliberately does not render them: the agent offers the user their next
  question, it does not interrogate them. That is the one place the main chat
  parts company with the FDE interview in `AgentStudioPanel/PlanChat.tsx`,
  where questioning the FDE is the point. A clarification renders as an
  ordinary answer whose `suggested_questions` become the chips.
- FDE language is concrete: “טול”, “חבילת FLAPI”, “קלט”, “פלט”, “שלב”,
  “פעיל לסוכן”, “כבוי”. “טיוטה” and “פורסם” are gone with publishing.
- **Studio editors edit one row, they do not append versions.** Each of
  `WorkflowEditor`, `PackageCatalog`, and `ContentStudio` holds an `editingId`:
  set, the form saves through `api.update*`; empty, through `api.create*`.
  Deriving "am I editing?" from the presence of `*_key` in the form is not
  enough — a key survives a delete and a load-from-plan — so the row's id is
  what the editors track. There is no publishing step: a save takes effect
  immediately, including on a route the agent is already selecting, and
  **`agent_enabled` is the only switch** —
  a checkbox on both editors, matching the one tools already had. A card shows
  "פעיל לסוכן" or "כבוי" with a matching dot, and dims via `is-off` when the
  agent will not select it; the dimming is a hint beside that text, never the
  only signal.
- **Each list header carries a `NewItemButton` (`StudioCommon`).** Because
  opening an item takes the form over, the only route back to a blank form
  was the cancel button that appears while editing — which reads as undo, not
  as a way to add something. Its `aria-label` names what would be created;
  "חדש" alone does not. It calls `startNew`, which is `reset` plus clearing
  the messages; `reset` on its own is what `save` calls after creating, where
  the success message still has to be visible.
- `SpecialistStudio` follows the same shape as the other editors: `editingId`
  chooses update over create, a specialist is deleted from its card, and
  "פעיל לסוכן" is the switch. Workflow ownership is always exclusive; the
  enabled-dependency checks apply only while the switch is on, which is what
  makes an unfinished specialist savable.
- The workflow form owns the primary assignment path: **סוכן אחראי** writes
  `summary_workflows.agent_id` on the same save that creates, edits, or enables
  the workflow. Once any specialists exist, an enabled workflow requires that
  choice. The specialist form reads and writes the same relationship through
  its derived `config.workflow_keys`; it is not a second source of truth.
- All four tabs delete. A Skill or prompt has nothing pinning it, so the
  confirm warns about the one surprise instead: a **built-in comes back on
  the next restart**, because seeding recreates a missing key — deleting one
  resets it to the shipped text rather than removing it. A tool is refused
  while a workflow uses it, and the backend's reason names those workflows,
  so it is surfaced as-is.
- AI workflow proposals are labeled as suggestions and loaded into the form
  for FDE review, never saved by the agent; missing tools show the required
  input and output contract.
- Fetch 1 ID requires a visibly labeled safe test identifier, shows a bounded
  preview, loads the inferred schema and empty examples into the unsaved tool
  form, and may fill empty description/instruction fields with editable model
  suggestions. Schema field chips support drag/drop plus a keyboard/touch click
  alternative; `x-summary: false` excludes a field only from model-facing
  summary facts, never from raw evidence.
- Agent Studio uses structured forms and a drag-to-connect step canvas,
  never an arbitrary code/SQL/HTTP editor.
- `WorkflowCanvas` is a view over the step array, not a second source of
  truth: an edge writes `input_source`, `input_field`, and `depends_on` on
  the target step, and the step cards below it stay the place every field is
  labeled and edited.
- A step node lists its tool's output fields (schema properties unioned with
  example keys, mirroring the backend's `_output_fields`), and **each field
  carries its own source handle**. Dragging from a field sets the source and
  the mapping in one gesture, so `input_field` is chosen by pointing at the
  value rather than recalled into a separate dropdown. Fields a later step
  reads are marked. An edge's endpoint can be dragged to another field or
  step to move it (`onEdgeUpdate`), which is why edges anchor to the field's
  handle rather than the node.
- The target handle sits on a labeled input row showing the selected tool's
  real `input_cube_parameter`, so an edge visibly connects output to input
  rather than disappearing into a generic card edge.
- A step holds one `input_source`, so a new edge replaces the old one.
  Deleting an edge — or deleting the step feeding it — returns the target to
  `workflow.id` **and clears `input_field`**, or the step keeps a mapping
  nothing points at. Cycles are refused at drag time rather than on save.
- `workflow.value` is a literal input stored in the target step's
  `input_value`. It has its own canvas source node and a visibly labeled value
  field in the step card; an empty saved value is invalid.
- Steps are sorted by dependency level in `workflowPayload`, because the
  backend resolves `steps.<key>` only against steps earlier in the array
  while the canvas lets an FDE wire a node backwards.
- **Two execution modes, inferred — never stored.** A step with no incoming
  connection lands in level 0, and the backend runs a whole level
  concurrently in a thread pool, so a workflow with nothing connected *is* a
  parallel bundle of tools and one long chain is a pipeline. There is no
  mode flag to set: connecting steps is the only control. `ExecutionMode`
  reads the graph and names what will run, and `stepLevels` must keep
  matching the backend's `step_levels` or the banner misreports it.
- Edges from `workflow.id` / `workflow.boundaries` / `workflow.value` carry
  `is-implicit` and
  are drawn faint and dashed. They are every unconnected step's default
  rather than a mapping the FDE drew, and at full strength a parallel bundle
  reads as a fan-out chain.
- The canvas expands to a fullscreen overlay, portalled to `document.body`
  so the studio form's scroll container cannot clip it. Like the interview
  drawer, it must stop `submit` and `Enter` at its own boundary — the canvas
  sits inside the editor `<form>`, so deleting a node by keyboard would
  otherwise save the draft. Esc closes it and body scroll is locked while it
  is open. Drag pans and the wheel zooms; panning by scroll would fight the
  form scrolling underneath. Remounting on expand refits the view.
- The tool interview ("שאלו את הסוכן") opens only after Fetch 1 ID has
  returned rows, and the disabled button carries a visible reason. The FDE owns
  the connection: it is seeded into every turn as fact, and the interview
  proposes only `name`, `description`, `agent_instructions`, `output_schema`,
  and the two examples, which the FDE then edits before saving.
- The Skill and specialist forms expose the same full interview drawer. The
  Skill interview writes a complete model instruction; the specialist
  interview receives the real Workflow/Skill catalogs and may return only
  assignable keys. Confirmation fills the current unsaved form and closes the
  drawer — the FDE still reviews and saves it.
- The interview drawer is portalled to `document.body`, but a portal still
  propagates events through the React tree — it must stop `submit` and `Enter`
  at its own boundary, or sending a message saves the editor's form.
- **The agent is also reachable per field**, on both studio editors. Each
  field carries its own small agent button (`FieldAgentPopover`), which opens
  the interview in a popover beside that field rather than in the drawer that
  covers the form — the value being negotiated stays next to the field it
  lands in. The client sends `focus_field`, the prompt scopes the interview to
  it, and **only that field is written back**: the turn carries the whole
  draft, so applying all of it would let a conversation about one field
  overwrite text the FDE edited by hand elsewhere. Each field keeps its own
  conversation. The popover is portalled like the drawer and carries the same
  `submit`/`Enter` guards for the same reason; being portalled, it is also
  positioned from viewport coordinates and must re-place on `scroll`
  (capturing, since scroll does not bubble) and `resize`.
- On the workflow editor the focusable parts are `name`, `role`,
  `description`, `system_prompt`, and **`steps` — the route itself**. `steps`
  is the one focus that does not write a string: it applies the plan's whole
  step array through `loadPlanSteps`, which unlike `loadPlan` leaves the name
  and description the FDE already wrote. It is offered only when the shared
  validation gate passed (`can_build`), since a plan naming a tool outside the
  catalog cannot be loaded onto the canvas.
- `description` and `system_prompt` answer two different questions and the UI
  must keep them apart: `description` is **what the route does** (read by an
  FDE choosing between routes), `system_prompt` is **how to read what came
  back** (read by the model that writes the section). The latter's label
  carries that as a visible hint, because the distinction is what makes the
  field fillable.
- A question may carry `options` — 2–4 clickable answers, the first being the
  agent's `recommendation`, which replace the lone "accept the recommendation"
  button when present. They are a shortcut past typing, never a closed menu:
  the composer stays available, and the agent returns `options` empty on
  questions whose honest answers are open-ended. A single option is dropped
  server-side, since one choice is not a choice.
- Respect reduced motion and preserve visible focus rings.
