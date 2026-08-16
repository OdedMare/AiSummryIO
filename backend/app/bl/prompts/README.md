# Prompts (`app/bl/prompts/`)

Prompt text as markdown, beside the code that sends it. These are product
wording that gets tuned by reading it, so they are files you can diff in a PR
rather than string constants buried in control flow.

```python
from app.bl import prompts
system = prompts.load("tool_interview")
```

## What belongs here — and what does not

This directory holds **engineering-owned** prompts: the ones that define how
an agent behaves, versioned with the code that depends on their shape.

**FDE-owned content stays in the `agent_content` table**, editable live in
Agent Studio without a deploy. Skills, the `workflow-planner` prompt, and a
workflow's `system_prompt` are all read from the database at call time. Do not
move those here — it would take away an ability the product already ships.

The rule: if changing the text requires changing code to stay correct, it is a
file. If an FDE should be able to change it on a Tuesday afternoon, it is
database content. A prompt read from the database may still keep its
**fallback** here.

## Files

| File | Sent by |
|---|---|
| `tool_interview.md` | `_ToolPlanner` — the tool interview |
| `workflow_interview.md` | `_WorkflowPlanner` — the workflow interview |
| `tool_metadata.md` | `_tool_metadata` — Fetch 1 ID suggestions |
| `shared/untrusted.md` | every prompt that reads user data |
| `shared/hebrew.md` | every FDE-facing prompt |
| `skill_interview.md` | `_SkillPlanner` — the Skill interview |
| `specialist_interview.md` | `_SpecialistPlanner` — the specialist interview |
| `shared/interview_method.md` | all four interviews |

## Includes

Composition is an include line, resolved by the loader:

```markdown
<!-- include: shared/untrusted.md -->
```

Targets resolve relative to this directory and may nest. A missing file or an
include cycle raises at load time rather than sending a silently truncated
prompt to the model.

## Caching

`load(name)` reads once per process. `load(name, reload=True)` re-reads from
disk, which is the point of having these as files — wording can be iterated
without a restart.

## Rules

- Never interpolate untrusted values into a prompt. User and FDE data travels
  in the JSON user message, which every prompt here is told to distrust.
- A prompt that names schema keys must stay in sync with `schemas.py`. The
  markdown is not validated against it.
- Keep Hebrew output instructions in `shared/hebrew.md` rather than restating
  them per prompt.
