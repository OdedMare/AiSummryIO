# HTTP boundary (`app/api/`)

Code used directly by FastAPI routes, without business logic or persistence.

| File | Owns |
|---|---|
| `models.py` | Pydantic request and response contracts |
| `auth.py` | Signed session cookies |

`main.py` is the only composition root and imports this package. Business
decisions stay under `bl/`; SQL stays under `dal/repository/`.

## Locked rules

- User-facing validation and authentication errors are Hebrew.
- Identifiers stay opaque strings, including values such as `00123`.
- Cookies remain `HttpOnly` and `SameSite=Lax`.
- Never log passwords, tokens, request bodies, or full identifiers.
- `PlanChatCreate.focus_field` names the one form field an interview is about;
  empty means the whole tool or workflow. Validation stays permissive here —
  each planner under `bl/` checks the name against the fields it may author, so
  an unknown value is ignored there rather than rejected at the boundary.
- `SkillPreviewSection` mirrors the section contract (`coverage`, `patterns`,
  `outliers`), so previewing a Skill exercises the same shape a real run
  produces. Adding a field to the section schema means adding it here too.
