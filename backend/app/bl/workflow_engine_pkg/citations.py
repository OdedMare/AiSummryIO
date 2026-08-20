"""Per-claim citations: the catalog, the public DTO, and validation.

A section has always carried `evidence_ids`, but `_safe_section` deliberately
withheld them from the final-summary call, so the model could not tag a claim
with a source and the UI could only cite at section granularity. This module
is what changes that safely.

Three rules hold it together, and they are the reason citations can be trusted:

- **The catalog is built in Python from evidence that was really saved.**
  `build` reads the sections' `evidence_ids` and the run's own evidence rows;
  a citation therefore exists only where a record exists. The model is never
  asked for a URL, a record id, or a source name it could invent.
- **The model chooses only from ids it was given.** `citation_ids` on a claim
  are validated against the catalog by `attach`, and an id that is not in it
  is dropped rather than rendered. The worst a bad model can do is cite
  nothing.
- **The internal record never leaves.** An entry keeps `records` and the
  step's raw rows so an excerpt can be cut from them; `public` is the only
  shape that reaches a client, and it carries no raw record.
"""

from typing import Dict, List, Optional

# A citation marker is read inline, next to the claim it supports, so the
# excerpt has to be glanceable rather than complete. The record itself is one
# click away in the evidence drawer, which is where the whole row belongs.
_EXCERPT_LIMIT = 160
_EXCERPT_FIELDS = 4

# Bounds what the final-summary call receives. A run over thousands of rows
# still cites at step granularity, so this is a cap on distinct sources, not
# on data — past it the payload costs more than the traceability it buys.
_MAX_CITATIONS = 40


def build(sections: List[dict], evidence: List[dict]) -> List[dict]:
    """One citation per persisted evidence row, in section order.

    `evidence` is the run's saved rows, keyed by id. A section naming an
    evidence id that was never persisted — a cached section, a dry run —
    simply contributes no citation, which is what keeps a marker from ever
    resolving to a missing record.
    """
    by_id = {item["id"]: item for item in evidence if item.get("id")}
    catalog: List[dict] = []
    for section in sections:
        for evidence_id in section.get("evidence_ids") or []:
            row = by_id.get(evidence_id)
            if row is None or len(catalog) >= _MAX_CITATIONS:
                continue
            catalog.append(_entry(len(catalog) + 1, section, row))
    return catalog


def _entry(number: int, section: dict, row: dict) -> dict:
    records = row.get("records") or []
    return {
        "citation_id": "c%d" % number,
        "evidence_id": row["id"],
        # The source record this citation resolves to: the evidence row, and
        # the step within the workflow that produced it.
        "source_id": row["id"],
        "workflow_id": section.get("workflow_id", ""),
        "workflow_key": section.get("workflow_key", ""),
        "step_key": row.get("step_key", ""),
        "label": section.get("name", "") or row.get("step_key", ""),
        "fields": _fields(records),
        "excerpt": _excerpt(records),
        "row_count": len(records),
    }


def _fields(records: List[dict]) -> List[str]:
    """The record's field names, in first-seen order.

    Names, not values: they say what the source can support without putting
    the data itself in a payload the model reads.
    """
    fields: List[str] = []
    for record in records[:_EXCERPT_FIELDS]:
        if not isinstance(record, dict):
            continue
        for key in record:
            if str(key) not in fields:
                fields.append(str(key))
    return fields[:_EXCERPT_FIELDS * 2]


def _excerpt(records: List[dict]) -> str:
    """A short, bounded rendering of the first record.

    Enough to recognize the row behind a marker without opening the drawer,
    and never the whole record — the drawer is what serves the full row, with
    pagination this cannot reproduce.
    """
    first = next(
        (item for item in records if isinstance(item, dict) and item), None
    )
    if first is None:
        return ""
    parts = [
        "%s: %s" % (key, value)
        for key, value in list(first.items())[:_EXCERPT_FIELDS]
        if value is not None
    ]
    text = " · ".join(parts)
    return text if len(text) <= _EXCERPT_LIMIT else text[:_EXCERPT_LIMIT] + "…"


def options(catalog: List[dict]) -> List[dict]:
    """What the final-summary model may cite from.

    Deliberately not the evidence: an id, a human label, and the field names
    it covers are enough to pick a source for a claim, and nothing here can
    be mistaken for data to summarize. That is what keeps citation selection
    from becoming a second, unbounded summarization pass.
    """
    return [
        {
            "citation_id": item["citation_id"],
            "label": item["label"],
            "step_key": item["step_key"],
            "fields": item["fields"],
            "row_count": item["row_count"],
        }
        for item in catalog
    ]


def public(entry: dict) -> dict:
    """The client-facing citation. Never the internal entry.

    `records` and every raw row stay behind: a citation is a pointer to a
    source plus enough metadata to render a marker, and the record itself is
    served by the evidence endpoints that already enforce ownership.
    """
    return {
        "citation_id": entry["citation_id"],
        "evidence_id": entry["evidence_id"],
        "source_id": entry["source_id"],
        "workflow_id": entry.get("workflow_id", ""),
        "workflow_key": entry.get("workflow_key", ""),
        "step_key": entry.get("step_key", ""),
        "label": entry.get("label", ""),
        "fields": list(entry.get("fields", [])),
        "excerpt": entry.get("excerpt", ""),
        "row_count": entry.get("row_count", 0),
    }


def attach(result: dict, catalog: List[dict]) -> dict:
    """Validate the model's citations and publish the catalog on the result.

    Every id a claim carries is checked against the catalog, so a marker can
    only ever point at evidence this run really stored. An unknown id is
    dropped silently rather than failing the run: a claim losing its marker
    degrades to the section-level traceability that existed before, while a
    hard failure would throw away an answer that is otherwise correct.
    """
    known = {item["citation_id"] for item in catalog}
    claims = []
    for claim in result.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("text", "")).strip()
        if not text:
            continue
        cited = [
            value for value in _texts(claim.get("citation_ids"))
            if value in known
        ]
        claims.append({"text": text, "citation_ids": cited})
    result["claims"] = claims
    result["citations"] = [public(item) for item in catalog]
    return result


def _texts(values) -> List[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(
        str(value) for value in values if isinstance(value, (str, int))
    ))


def find(catalog: List[dict], citation_id: str) -> Optional[dict]:
    """The catalog entry for an id, or None when it is unknown."""
    for item in catalog:
        if item.get("citation_id") == citation_id:
            return item
    return None


def from_result(result: dict) -> List[dict]:
    """The stored public citations of a finished run.

    Runs written before citations existed have no `citations` key, so this
    returns an empty list and every caller degrades to no citation rather
    than failing on an older thread.
    """
    if not isinstance(result, dict):
        return []
    citations = result.get("citations")
    return [item for item in citations if isinstance(item, dict)] \
        if isinstance(citations, list) else []


def resolve(runs: List[dict], citation_id: str) -> Optional[Dict]:
    """Find one citation across a conversation's finished runs, newest first.

    A follow-up cites what an earlier turn said, so resolution has to search
    the thread rather than the current run. Newest first because a repeated
    marker in a long thread means the most recent one.
    """
    for run in reversed(list(runs)):
        for item in from_result(run.get("result") or {}):
            if item.get("citation_id") == citation_id:
                found = dict(item)
                found["run_id"] = run.get("id", "")
                return found
    return None
