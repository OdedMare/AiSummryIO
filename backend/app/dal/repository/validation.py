"""Pure workflow persistence validation."""

from typing import List


def step_levels(steps: List[dict]) -> List[List[dict]]:
    """Group steps into dependency levels, preserving declared order.

    A level holds steps whose dependencies are all satisfied by earlier
    levels, so its members are independent of one another and may run
    concurrently. Steps that declare no dependency all land in level 0, which
    is how a workflow becomes a set of parallel tools rather than a chain.

    Validation already rejects forward references, so every step is reachable
    and no cycle can survive to this point.
    """
    levels, placed = [], set()
    remaining = list(steps)
    while remaining:
        level = [
            step for step in remaining
            if _dependencies(step) <= placed
        ]
        if not level:
            raise ValueError("קיימת תלות מעגלית בין שלבי התהליך")
        levels.append(level)
        placed.update(step["key"] for step in level)
        remaining = [step for step in remaining if step not in level]
    return levels


def _dependencies(step: dict) -> set:
    """Every step key this step must wait for, declared or implied by input."""
    declared = set(step.get("depends_on") or [])
    source = step.get("input_source", "workflow.id")
    parts = source.split(".")
    if len(parts) >= 2 and parts[0] == "steps":
        declared.add(parts[1])
    return declared


def validate_steps(steps: List[dict]) -> None:
    keys = [step["key"] for step in steps]
    if len(keys) != len(set(keys)):
        raise ValueError("מפתחות השלבים חייבים להיות ייחודיים")
    seen = set()
    for step in steps:
        _validate_step(step, seen)
        seen.add(step["key"])


def _validate_step(step: dict, seen: set) -> None:
    missing = set(step.get("depends_on", [])) - seen
    if missing:
        raise ValueError(
            "שלב תלוי בשלב מאוחר או לא קיים: " + ", ".join(missing)
        )
    source = step.get("input_source", "workflow.id")
    if source == "workflow.id":
        return
    _validate_source(step, source, seen)


def _validate_source(step: dict, source: str, seen: set) -> None:
    parts = source.split(".")
    if len(parts) != 2 or parts[0] != "steps" or parts[1] not in seen:
        raise ValueError("מקור הקלט חייב להיות שלב מוקדם יותר")
    if not step.get("input_field", "").strip():
        raise ValueError("נדרש שדה פלט למיפוי משלב קודם")
    if parts[1] not in set(step.get("depends_on", [])):
        raise ValueError(
            "שלב הקורא מפלט שלב אחר חייב להצהיר עליו בתלויות: " + parts[1]
        )
