# SumOrAI frontend context

Read this before changing `frontend/`.

## Product

Hebrew-first (`lang="he"`, `dir="rtl"`) workspace for complete summaries by
identifier. The UI reuses LocatoAI's shell: dark history/navigation rail,
bounded conversation, bottom composer, Settings, tool catalog, and Agent
Studio. It also has a small optional map picker in the composer
(`components/MapWorkspace/`), ported from LocatoAI: one drawn polygon or
rectangle scopes the request. It is a picker, not LocatoAI's full map
workspace — no result layers, no layer catalog, no plan pipeline.

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

## State and API

`components/AppShell/index.tsx` owns the active conversation, root string ID,
question, run polling, history, theme, Settings, and Agent Studio visibility.
`services/api.ts` is the browser's only backend boundary.

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
- FDE language is concrete: “טול”, “חבילת FLAPI”, “קלט”, “פלט”, “שלב”,
  “טיוטה”, “פורסם”.
- AI workflow proposals are labeled as suggestions and loaded only as drafts
  for FDE review; missing tools show the required input and output contract.
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
- A step holds one `input_source`, so a new edge replaces the old one.
  Deleting an edge — or deleting the step feeding it — returns the target to
  `workflow.id` **and clears `input_field`**, or the step keeps a mapping
  nothing points at. Cycles are refused at drag time rather than at publish.
- Steps are sorted by dependency level in `workflowPayload`, because the
  backend resolves `steps.<key>` only against steps earlier in the array
  while the canvas lets an FDE wire a node backwards.
- The tool interview ("שאלו את הסוכן") opens only after Fetch 1 ID has
  returned rows, and the disabled button carries a visible reason. The FDE owns
  the connection: it is seeded into every turn as fact, and the interview
  proposes only `name`, `description`, `agent_instructions`, `output_schema`,
  and the two examples, which the FDE then edits before saving.
- The interview drawer is portalled to `document.body`, but a portal still
  propagates events through the React tree — it must stop `submit` and `Enter`
  at its own boundary, or sending a message saves the editor's form.
- Respect reduced motion and preserve visible focus rings.
