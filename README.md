# AiSummryIO

Hebrew-first agent application for evidence-backed summaries by identifier.
FDEs configure versioned FLAPI packages, workflows, skills, prompts, and
examples; users provide one identifier and receive a progressive full summary.

## Run

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Set `AISUMMRY_ADMIN_PASSWORD` before first start. In an air-gapped environment,
make the internal `flunks` wheel available to the backend build.

