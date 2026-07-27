# Business logic (`app/bl/`)

Where decisions are made. `bl/` decides *what* to run and *how* to interpret
the result; `dal/` only fetches and sends. Nothing here imports `psycopg`,
`openai`, or `flunks` directly — it goes through the repository, the LLM
client, and the provider it was constructed with.

| File | Lines | Owns |
|---|---|---|
| `workflow_engine.py` | 857 | `SummaryService` — execution, synthesis, planning |
| `jobs.py` | 72 | `JobRunner` — the bounded background queue |

`workflow_engine_pkg/` holds the behavior modules the facade delegates to,
including `conversational_planning.py` and its prompts in
`planning_prompts.py`.

## `SummaryService` (`workflow_engine.py`)

Constructed with `(repository, provider, llm, settings_store)` — all four are
injected, which is what makes the whole service testable without a database,
a model, or a flunks wheel.

### Entry points

| Method | Trigger | Behavior |
|---|---|---|
| `full_summary` | A new question | Runs **all** published `baseline`/`both` workflows |
| `follow_up` | A message in an existing conversation | Reuses prior evidence; runs **one** `detail`/`both` workflow or one FDE-approved tool, or answers from cache |
| `plan_workflow` | FDE asks for a workflow | Drafts one from catalog tools; never publishes |
| `plan_tool_chat` | FDE discusses a tool | One conversational turn; opens on a sample the FDE already ran and proposes only the summary-facing fields |
| `plan_workflow_chat` | FDE discusses a workflow | One conversational turn; draft passes the same validation gate |
| `inspect_tool` | FDE previews a package | One identifier, bounded preview, inferred schema, no persistence |
| `dry_run` | FDE tests a workflow | Executes with `save_evidence=False` |
| `preview_skill` | FDE tests Skill wording | Runs one Skill against sample sections; no packages, no persistence |

`follow_up` may return `needs_clarification` instead of running anything, when
`_select_detail` cannot confidently pick a workflow. It suggests the available
workflow and tool names rather than guessing.

### The execution path

`_execute` → `_execute_workflow` (per workflow, in a thread pool bounded by
`max_parallel_workflows`) → `_run_package` → the FLAPI provider.

`_execute_workflow` walks a workflow's steps in order. Each step:

1. loads its version-pinned package,
2. resolves identifiers via `_identifiers`,
3. runs the package — **a failure is caught, recorded as a warning, and the
   step yields `[]`**; it does not abort the workflow,
4. stores rows in `context["steps"][key]` for later steps to read,
5. saves an evidence row unless this is a dry run.

That failure-tolerance is the "partial success" rule: a workflow with warnings
returns `status: "partial"` and keeps every section that did succeed.

### `_identifiers` — the input contract

A step's `input_source` is one of exactly three shapes:

- `workflow.id` — the conversation's root identifier, as a string.
- `workflow.boundaries` — the area drawn on the map, serialized by
  `common/geometry.py` to an OGC `MULTIPOLYGON` WKT string. **Raises a clear
  Hebrew error when no area was drawn.** To FLAPI this is just another opaque
  string.
- `steps.<key>` — an earlier step's output, read through `input_field`. Values
  that are lists fan out; `None` is skipped; the result is deduplicated while
  preserving order (`dict.fromkeys`).

Forward references and undeclared dependencies are rejected earlier, at
validation time, by `Repository._validate_steps`.

### `_run_package` — where `input_mode` is applied

`many` sends every identifier in one package call; `single` calls the package
once per identifier and concatenates. The provider itself never sees
`input_mode` — it always receives a ready list.

### Synthesis

`_section_summary` summarizes one workflow's facts; `_final_summary` merges
sections into the answer. Both call the LLM with a JSON schema:

- `_SECTION_SCHEMA` — `summary`, `facts`, `warnings`, `suggested_questions`.
  A workflow's own `output_schema` **extends** this shared contract, and the
  extra fields come back under `section.fields` (`_merge_output_schema`).
- `_FINAL_SCHEMA` — adds `key_findings`, `risks`, `missing_data`, and
  `skill_results`.

### Skills — one LLM call each

`_run_skills` runs **every selected Skill in its own call** under
`_SKILL_SCHEMA` (`summary`, `items`, `sources`), with that Skill's full
instructions as the system prompt. One shared call made the Skills compete for
a single token budget and one generic schema; a dedicated call is why detailed
Skill instructions are worth writing. The shared `_final_summary` call is
therefore told to return `skill_results` empty.

Skills are independent, so they run concurrently (`_skill_workers`, bounded by
`max_parallel_workflows` and by the 3-Skill selection limit). Results are
reordered to the user's selection rather than completion order, and a Skill
that fails degrades to a stated reason via `_skill_failure` without discarding
another Skill's result.

`_valid_skill_result` drops any cited source that is not a real section,
enforcing the rule that **claims require evidence references**. It also records
the original citations under `_raw_sources`, which `preview_skill` surfaces to
an FDE and `_run_skills` strips before any result reaches a user.

`preview_skill` runs unsaved Skill instructions against caller-supplied sample
sections — no packages, no persistence — so a wording problem can be separated
from a package failure.

### Planning and tools

`plan_workflow` sends the FDE prompt plus a catalog of existing tools to the
LLM under `_WORKFLOW_PLAN_SCHEMA`, then runs `_validated_plan`, which rejects
any step whose `package_version_id` is not in the catalog. The model may report
`missing_tools` describing a contract it needs, but it can never invent a
package call, HTTP request, SQL, or mapping. Output is always a **draft**.

## `JobRunner` (`jobs.py`)

Two pools, so an interactive follow-up never waits behind a long full summary:

- `_follow_up_pool` — exactly 1 worker, for `kind == "follow_up"`.
- `_full_pool` — `max(2, workers) - 1` workers, for everything else.

`submit()` deduplicates through `_submitted` under a lock, so the same run is
never executed twice. `recover()` re-submits runs left `queued` by a restart.
`_execute` sets `running`, invokes the service with a `progress` callback that
writes progress to the run row, and always finishes by marking the run
`completed` / `partial` / `failed` — the `finally` block clears `_submitted`
even on failure.

## Rules

- Only published, version-pinned workflows or the latest FDE-approved
  standalone tool version may be selected.
- Package failures stay visible as warnings and never discard successful
  sections.
- Claims require evidence references.
- Business logic stays here; SQL stays in `dal/repository/`; external calls
  stay in `dal/`.
