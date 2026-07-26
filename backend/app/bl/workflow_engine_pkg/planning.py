"""Tool inspection and FDE workflow planning."""

import json
from typing import List

from app.dal.repository import Repository
from app.bl.workflow_engine_pkg.schemas import WORKFLOW_PLAN_SCHEMA


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
    limit = 20
    return {
        "row_count": len(records),
        "records": records[:limit],
        "truncated": len(records) > limit,
        "output_schema": infer_output_schema(records),
    }


def validated_plan(plan: dict, tools: List[dict]) -> dict:
    missing = list(plan.get("missing_tools", []))
    steps = _known_steps(plan.get("steps", []), tools, missing)
    steps = _valid_steps(steps, missing)
    return {
        "can_build": bool(steps),
        "name": str(plan.get("name", "")),
        "description": str(plan.get("description", "")),
        "role": _role(plan.get("role")),
        "rationale": str(plan.get("rationale", "")),
        "system_prompt": str(plan.get("system_prompt", "")),
        "steps": steps,
        "missing_tools": missing,
    }


def _known_steps(steps, tools, missing) -> List[dict]:
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
    try:
        Repository._validate_steps(steps)
        return steps
    except ValueError as exc:
        missing.append({
            "name": "מיפוי שלבים", "reason": str(exc),
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
