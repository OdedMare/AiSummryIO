"""Turn FastAPI request-validation failures into one Hebrew sentence.

FastAPI answers a rejected body with ``detail`` as a list of error objects.
A client that renders that value directly shows "[object Object]", so the
HTTP boundary collapses it here into readable text naming the offending
field.
"""

from typing import Any, Dict

_MAX_REPORTED = 3

_FIELD_NAMES = {
    "name": "שם",
    "role": "תפקיד",
    "steps": "שלבים",
    "key": "מפתח שלב",
    "package_version_id": "טול",
    "input_source": "מקור הקלט",
    "input_field": "שדה הקלט",
    "depends_on": "תלויות",
    "output_schema": "חוזה פלט",
    "examples": "דוגמאות",
    "prompt": "הנחיה",
    "root_id": "מזהה",
    "question": "שאלה",
}


def format_validation_error(exc) -> str:
    errors = list(getattr(exc, "errors", list)() or [])
    if not errors:
        return "הבקשה נדחתה: נתונים לא תקינים"
    reported = [_one_error(item) for item in errors[:_MAX_REPORTED]]
    remaining = len(errors) - len(reported)
    if remaining > 0:
        reported.append("ועוד %d שגיאות" % remaining)
    return "; ".join(reported)


def _one_error(error: Dict[str, Any]) -> str:
    location = _location(error.get("loc", ()))
    message = str(error.get("msg", "ערך לא תקין")).strip()
    message = _strip_prefix(message)
    if not location:
        return message
    return "%s: %s" % (location, message)


def _strip_prefix(message: str) -> str:
    """Drop Pydantic's English "Value error, " wrapper around our own text."""
    prefix = "Value error, "
    return message[len(prefix):] if message.startswith(prefix) else message


def _location(loc) -> str:
    parts = [_part(item) for item in loc if item != "body"]
    return " → ".join(part for part in parts if part)


def _part(item) -> str:
    if isinstance(item, int):
        return "פריט %d" % (item + 1)
    text = str(item)
    return _FIELD_NAMES.get(text, text)
