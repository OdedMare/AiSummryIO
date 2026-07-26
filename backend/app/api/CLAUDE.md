# HTTP boundary (`app/api/`)

Code used directly by FastAPI routes, without business logic or persistence.

| File | Owns |
|---|---|
| `models.py` | Pydantic request and response contracts |
| `auth.py` | Signed admin tokens, session cookies, and password verification |

`main.py` is the only composition root and imports this package. Business
decisions stay under `bl/`; SQL stays under `dal/repository/`.

## Locked rules

- User-facing validation and authentication errors are Hebrew.
- Identifiers stay opaque strings, including values such as `00123`.
- Cookies remain `HttpOnly` and `SameSite=Lax`.
- Never log passwords, tokens, request bodies, or full identifiers.
