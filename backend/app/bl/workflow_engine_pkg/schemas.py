"""JSON schemas constraining every LLM call, plus the section contract merge.

These are the wire contracts sent to ``llm.complete_json``. They are kept
separate from the Pydantic models in ``models.py``: these describe what the
model is *asked* to return, the Pydantic models describe what the rest of the
backend is *guaranteed* to receive.
"""

from typing import Any, Dict

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
    },
    "required": ["summary", "facts", "warnings", "suggested_questions"],
    "additionalProperties": False,
}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
        "skill_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill_key": {"type": "string"},
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "items": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "sources": {
                        "type": "array", "items": {"type": "string"}
                    },
                },
                "required": [
                    "skill_key", "name", "summary", "items", "sources"
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "summary", "key_findings", "risks",
        "missing_data", "suggested_questions", "skill_results",
    ],
    "additionalProperties": False,
}

SKILL_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "items", "sources"],
    "additionalProperties": False,
}

WORKFLOW_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "role": {
            "type": "string",
            "enum": ["baseline", "detail", "both"],
        },
        "rationale": {"type": "string"},
        "system_prompt": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "name": {"type": "string"},
                    "package_version_id": {"type": "string"},
                    "depends_on": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "input_source": {"type": "string"},
                    "input_field": {"type": "string"},
                    "summary_prompt": {"type": "string"},
                },
                "required": [
                    "key", "name", "package_version_id", "depends_on",
                    "input_source", "input_field", "summary_prompt",
                ],
                "additionalProperties": False,
            },
        },
        "missing_tools": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reason": {"type": "string"},
                    "input_description": {"type": "string"},
                    "output_description": {"type": "string"},
                },
                "required": [
                    "name", "reason",
                    "input_description", "output_description",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "name", "description", "role", "rationale",
        "system_prompt", "steps", "missing_tools",
    ],
    "additionalProperties": False,
}

_PLAN_CHAT_BASE_PROPERTIES = {
    "reply": {"type": "string"},
    "questions": {"type": "array", "items": {"type": "string"}},
    "ready": {"type": "boolean"},
}

TOOL_PLAN_CHAT_SCHEMA = {
    "type": "object",
    "properties": dict(
        _PLAN_CHAT_BASE_PROPERTIES,
        needs_inspection={"type": "boolean"},
        draft={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "package_id": {"type": "string"},
                "input_cube_name": {"type": "string"},
                "input_cube_parameter": {"type": "string"},
                "output_cube_name": {"type": "string"},
                "input_mode": {
                    "type": "string", "enum": ["single", "many"],
                },
                "description": {"type": "string"},
                "agent_instructions": {"type": "string"},
            },
            "required": [
                "name", "package_id", "input_cube_name",
                "input_cube_parameter", "output_cube_name", "input_mode",
                "description", "agent_instructions",
            ],
            "additionalProperties": False,
        },
    ),
    "required": [
        "reply", "questions", "ready", "needs_inspection", "draft",
    ],
    "additionalProperties": False,
}

WORKFLOW_PLAN_CHAT_SCHEMA = {
    "type": "object",
    "properties": dict(
        _PLAN_CHAT_BASE_PROPERTIES,
        draft=WORKFLOW_PLAN_SCHEMA,
    ),
    "required": ["reply", "questions", "ready", "draft"],
    "additionalProperties": False,
}

TOOL_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "agent_instructions": {"type": "string"},
        "field_descriptions": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
    "required": [
        "description", "agent_instructions", "field_descriptions",
    ],
    "additionalProperties": False,
}

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["use_cached", "workflow", "tool", "clarify"],
        },
        "workflow_key": {"type": ["string", "null"]},
        "tool_version_id": {"type": ["string", "null"]},
        "clarification": {"type": ["string", "null"]},
    },
    "required": [
        "action", "workflow_key", "tool_version_id", "clarification"
    ],
    "additionalProperties": False,
}


def merge_output_schema(output_schema: Any) -> Dict[str, Any]:
    """Extend the section contract with the workflow's own fields.

    The frontend renders summary/facts/warnings/suggested_questions, so an
    FDE schema adds fields rather than replacing them. A malformed schema
    degrades to the shared contract instead of failing the run.
    """
    if not isinstance(output_schema, dict):
        return SECTION_SCHEMA
    extra = output_schema.get("properties")
    if not isinstance(extra, dict) or not extra:
        return SECTION_SCHEMA
    properties = dict(SECTION_SCHEMA["properties"])
    for name, definition in extra.items():
        if name not in properties and isinstance(definition, dict):
            properties[name] = definition
    required = list(SECTION_SCHEMA["required"])
    for name in output_schema.get("required", []):
        if name in properties and name not in required:
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
