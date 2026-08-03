"""Tool inspection and FDE workflow planning."""

import json
from typing import List

from app.common.errors import AgentError
from app.dal.repository import Repository
from app.bl import prompts
from app.bl.workflow_engine_pkg.schemas import (
    TOOL_METADATA_SCHEMA, WORKFLOW_PLAN_SCHEMA,
)


def plan_workflow(service, prompt: str) -> dict:
    tools = service._repository.list_packages()
    if not tools:
        return _empty_catalog_plan()
    system = service._repository.published_content(
        "workflow-planner",
        "הרכב טיוטת workflow רק מהטולים שסופקו; ציין מה חסר.",
    )
    payload = json.dumps(
        {"fde_prompt": prompt, "available_tools": tool_catalog(tools)},
        ensure_ascii=False,
    )
    plan = service._llm.complete_json(system, payload, WORKFLOW_PLAN_SCHEMA)
    return validated_plan(plan, tools)


def _empty_catalog_plan() -> dict:
    return {
        "can_build": False,
        "name": "", "description": "", "role": "detail",
        "rationale": "אין טולים בקטלוג.", "system_prompt": "", "steps": [],
        "missing_tools": [{
            "name": "טול ראשון",
            "reason": "הקטלוג ריק ולכן אי אפשר להרכיב workflow.",
            "input_description": "מזהה ראשי כמחרוזת",
            "output_description": "עובדות מובנות לסיכום",
        }],
    }


def tool_catalog(tools: List[dict]) -> List[dict]:
    return [_catalog_item(tool) for tool in tools]


def _catalog_item(tool: dict) -> dict:
    return {
        "package_version_id": tool["id"],
        "name": tool["name"],
        "description": tool.get("description", ""),
        "agent_instructions": tool.get("agent_instructions", ""),
        "input_mode": tool["input_mode"],
        "input_parameter": tool["input_cube_parameter"],
        "output_fields": _output_fields(tool),
        "summary_fields": summary_fields(tool),
    }


def _output_fields(tool: dict) -> List[str]:
    schema = tool.get("output_schema", {})
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    example_fields = {
        str(field)
        for row in tool.get("example_output", []) if isinstance(row, dict)
        for field in row
    }
    return sorted(set(properties) | example_fields)


def inspect_tool(service, package: dict, root_id: str) -> dict:
    package = dict(package)
    package["package_key"] = package.get("package_key") or "fde-inspection"
    records = service._run_package(package, [str(root_id)])
    schema = infer_output_schema(records)
    suggestions = _tool_metadata(service, package, schema, records)
    _merge_field_metadata(
        schema, package.get("output_schema"), suggestions["field_descriptions"]
    )
    limit = 20
    return {
        "row_count": len(records),
        "records": records[:limit],
        "truncated": len(records) > limit,
        "output_schema": schema,
        "metadata_suggestions": {
            "description": suggestions["description"],
            "agent_instructions": suggestions["agent_instructions"],
        },
    }


def _tool_metadata(service, package, schema, records) -> dict:
    empty = {
        "description": "", "agent_instructions": "",
        "field_descriptions": {},
    }
    if service._llm is None or not records:
        return empty
    payload = json.dumps({
        "tool_name": str(package.get("name", ""))[:200],
        "package_id": str(package.get("package_id", ""))[:200],
        "input_parameter": str(
            package.get("input_cube_parameter", "")
        )[:200],
        "output_cube": str(package.get("output_cube_name", ""))[:200],
        "output_schema": schema,
        "sample_data": _metadata_sample(records),
    }, ensure_ascii=False)
    try:
        generated = service._llm.complete_json(
            prompts.load("tool_metadata"), payload, TOOL_METADATA_SCHEMA
        )
    except AgentError:
        return empty
    descriptions = generated.get("field_descriptions", {})
    public_fields = set(schema["properties"])
    return {
        "description": _bounded_text(generated.get("description"), 2000),
        "agent_instructions": _bounded_text(
            generated.get("agent_instructions"), 3000
        ),
        "field_descriptions": {
            str(field): _bounded_text(description, 500)
            for field, description in descriptions.items()
            if str(field) in public_fields
        } if isinstance(descriptions, dict) else {},
    }


def _metadata_sample(records):
    fields = _public_fields(records)[:20]
    return [{
        field: str(row[field])[:200]
        for field in fields if field in row and row[field] is not None
    } for row in records[:10] if isinstance(row, dict)]


def _bounded_text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _merge_field_metadata(schema, previous, descriptions) -> None:
    old_properties = (
        previous.get("properties", {}) if isinstance(previous, dict) else {}
    )
    for field, definition in schema["properties"].items():
        old = old_properties.get(field, {})
        if isinstance(old, dict):
            if isinstance(old.get("description"), str):
                definition["description"] = old["description"][:500]
            if isinstance(old.get("x-summary"), bool):
                definition["x-summary"] = old["x-summary"]
        definition.setdefault("description", descriptions.get(field, ""))
        definition.setdefault("x-summary", True)


def summary_fields(tool: dict) -> List[str]:
    schema = tool.get("output_schema", {})
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if not any(
        isinstance(definition, dict)
        and isinstance(definition.get("x-summary"), bool)
        for definition in properties.values()
    ):
        return _output_fields(tool)
    return [
        str(field) for field, definition in properties.items()
        if not isinstance(definition, dict)
        or definition.get("x-summary", True)
    ]


def validated_plan(plan: dict, tools: List[dict]) -> dict:
    """Shape one model-proposed plan into a draft the form can always load.

    The JSON schema sent with the request is a *request*, not a guarantee:
    ``OpenAIJsonClient`` degrades from `json_schema` to `json_object` to plain
    text, so against a server that ignores strict schemas every field here can
    arrive as the wrong type. Coercing rather than trusting is what keeps a
    malformed reply a rejected draft instead of an uncaught ``AttributeError``
    that reaches the FDE as a bare 500.
    """
    plan = plan if isinstance(plan, dict) else {}
    missing = _missing_tools(plan.get("missing_tools"))
    steps = _known_steps(plan.get("steps"), tools, missing)
    steps = _valid_steps(steps, missing)
    return {
        "can_build": bool(steps),
        "name": _text(plan.get("name")),
        "description": _text(plan.get("description")),
        "role": _role(plan.get("role")),
        "rationale": _text(plan.get("rationale")),
        "system_prompt": _text(plan.get("system_prompt")),
        "steps": steps,
        "missing_tools": missing,
    }


def _text(value) -> str:
    """A model-supplied string, or "" — never `str()` of a dict or None.

    `str(None)` would put the literal "None" in a field the FDE reads, and
    `str({...})` a Python repr; both are worse than an empty field.
    """
    return value if isinstance(value, str) else ""


def _missing_tools(value) -> List[dict]:
    """The model's own gap report, kept only where it is really a list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _known_steps(steps, tools, missing) -> List[dict]:
    # A non-list `steps`, or an entry that is not an object, is a malformed
    # reply rather than a plan naming an unknown tool — but the FDE outcome is
    # the same either way: nothing loadable, and a stated reason.
    if not isinstance(steps, list) or not all(
        isinstance(step, dict) for step in steps
    ):
        missing.append({
            "name": "מבנה שלבים לא תקין",
            "reason": "הצעת המודל לא הוחזרה במבנה שלבים תקין.",
            "input_description": "", "output_description": "",
        })
        return []
    steps = list(steps)
    valid_ids = {tool["id"] for tool in tools}
    if all(step.get("package_version_id") in valid_ids for step in steps):
        return steps
    missing.append({
        "name": "טול שלא קיים בקטלוג",
        "reason": "הצעת המודל כללה מזהה טול שאינו קיים.",
        "input_description": "", "output_description": "",
    })
    return []


def _valid_steps(steps, missing) -> List[dict]:
    # `validate_steps` indexes `step["key"]` and calls `.split` on
    # `input_source`, so a step missing a key or carrying a non-string source
    # raises KeyError/AttributeError/TypeError rather than ValueError. Those
    # are the same situation to the FDE — an unusable proposal — so they are
    # reported the same way instead of escaping as a 500.
    try:
        Repository._validate_steps(steps)
        return steps
    except ValueError as exc:
        reason = str(exc)
    except (AttributeError, KeyError, TypeError):
        reason = "הצעת המודל כללה שלב עם מבנה שדות לא תקין."
    missing.append({
        "name": "מיפוי שלבים", "reason": reason,
        "input_description": "פלט משלב מוקדם",
        "output_description": "מזהה קלט לשלב הבא",
    })
    return []


def _role(value: str) -> str:
    return value if value in ("baseline", "detail", "both") else "detail"


def infer_output_schema(records: List[dict]) -> dict:
    fields = _public_fields(records)
    return {
        "type": "object",
        "properties": {
            field: {"type": _field_type(records, field)} for field in fields
        },
        "required": [
            field for field in fields
            if records and all(
                isinstance(row, dict) and field in row for row in records
            )
        ],
        "additionalProperties": True,
    }


def _public_fields(records: List[dict]) -> List[str]:
    return sorted({
        str(key) for row in records if isinstance(row, dict)
        for key in row if not str(key).startswith("_")
    })


def _field_type(records: List[dict], field: str):
    types = {
        json_type(row[field]) for row in records
        if isinstance(row, dict) and field in row
    }
    if "number" in types:
        types.discard("integer")
    ordered = [
        item for item in (
            "string", "number", "integer", "boolean",
            "array", "object", "null",
        ) if item in types
    ]
    return ordered[0] if len(ordered) == 1 else ordered


def json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"
