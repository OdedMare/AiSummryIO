"""Pure workflow persistence validation."""

from typing import List


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
