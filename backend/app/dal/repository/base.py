"""Shared connection and query primitives for repository modules."""

import re
import uuid
from typing import List

from app.common.errors import NotFoundError
from app.dal.database.postgres import connect

_KEY_RE = re.compile(r"[^a-z0-9_-]+")


def new_id() -> str:
    return str(uuid.uuid4())


def slug(value: str) -> str:
    result = _KEY_RE.sub("-", value.strip().lower()).strip("-")
    return result or new_id()


class RepositoryBase:
    def __init__(self, settings_store):
        self._store = settings_store

    def health(self) -> dict:
        with connect(self._store) as connection:
            connection.execute("SELECT 1").fetchone()
        return {"database": "ok"}

    def _key_taken(self, table: str, key_name: str, key_value: str) -> bool:
        """Whether `key_value` already names a row in `table`.

        A key is one row now, so creating over an existing key is a mistake
        rather than a new version. The unique index is what actually
        guarantees it; this is here to answer with a readable Hebrew message
        instead of a driver constraint violation.
        """
        query = "SELECT 1 FROM %s WHERE %s=%%s LIMIT 1"
        return bool(self._all(query % (table, key_name), (key_value,)))

    def _one(self, query: str, params=()) -> dict:
        rows = self._all(query, params)
        if not rows:
            raise NotFoundError("הפריט לא נמצא")
        return rows[0]

    def _all(self, query: str, params=()) -> List[dict]:
        with connect(self._store) as connection:
            rows = connection.execute(query, params).fetchall()
            connection.commit()
        return [dict(row) for row in rows]
