# Scripts (`scripts/`)

Operator tools that talk to a **running** service over HTTP. Nothing here is
imported by the service, and nothing here reaches into the database or into
`bl/`/`dal/` — a script is an API client like the browser is, so it can only do
what the API already allows.

| Script | Does |
|---|---|
| `area_batch.py` | Runs every area in an Excel sheet through `/api/v1/summaries` and writes the answers back into the sheet |

## `area_batch.py`

```bash
cd backend
pip install openpyxl                                   # not a service dependency
python scripts/area_batch.py --workbook areas.xlsx --dry-run
python scripts/area_batch.py --workbook areas.xlsx
```

Configuration is the `CONFIG` block at the top of the file: the workbook, the
column holding the area, the questions to ask, which field of each answer goes
into which column, and the cooldown. Every value there has a command-line
override for a one-off run (`--help`).

What it is built around:

- **One area per row**, written as WKT (`MULTIPOLYGON`/`POLYGON`, with or
  without an `SRID=` prefix) or as GeoJSON. `common/geometry.py` parses the WKT
  and the API takes it from there — the script never converts coordinates.
- **`/api/v1`, not `/api`.** The versioned prefix is the one meant for
  programmatic clients; the unversioned one belongs to the UI.
- **One `httpx.Client` for the whole batch.** A conversation is owned by the
  signed session cookie that created it, so a follow-up sent from a fresh
  client would be refused.
- **Follow-ups by default.** The first question opens the conversation and pays
  for the packages; the rest ask inside it and reuse the saved evidence.
  `--new-conversation` runs each question from scratch instead.
- **Sequential, with a cooldown before each call except the first.** A run fans
  out to FLAPI and to the model, and the UI is using the same service.
- **Saved after every row**, so an interrupted batch keeps what it finished.
- **Blank means "never asked".** A finished run fills every column it maps,
  writing `—` where the answer itself was empty. That is what lets a re-run
  resume: a question whose columns are filled is skipped, and one that failed
  (answer column still blank, error column explaining why) is asked again.
- **A bad row is that row's problem.** An unparsable area or a failed run is
  recorded and the batch moves on.

Tests live with everything else in [tests/test_core.py](../tests/test_core.py)
and use a fake client, so they never open a socket.
