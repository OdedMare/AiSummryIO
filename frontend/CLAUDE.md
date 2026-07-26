# AiSummryIO frontend context

Read this before changing `frontend/`.

## Product

Hebrew-first (`lang="he"`, `dir="rtl"`) workspace for complete summaries by
identifier. The UI reuses LocatoAI's shell: dark history/navigation rail,
bounded conversation, bottom composer, Settings, tool catalog, and Agent
Studio. There is no map.

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

An initial request posts `{root_id, question}`. The API returns a persistent
run ID; poll it until complete while rendering progressive workflow sections.
Follow-ups post to the same conversation and retain the original ID/evidence.

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
  preview, and loads only the inferred schema into the unsaved tool form.
- Agent Studio uses structured forms and a read-only dependency preview,
  never an arbitrary code/SQL/HTTP editor.
- Respect reduced motion and preserve visible focus rings.
