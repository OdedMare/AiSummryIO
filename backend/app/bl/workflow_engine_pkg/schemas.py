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
        # What the section covers, stated by the model rather than inferred by
        # a reader from prose. A summary that says "412 rows over 3 steps"
        # cannot silently imply coverage it did not have.
        "coverage": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        # Distributions and ranges kept apart from individual facts. Mixing
        # them made a single record and a 300-record split read as equals.
        "patterns": {"type": "array", "items": {"type": "string"}},
        "outliers": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
    },
    "required": [
        "summary", "coverage", "facts", "patterns", "outliers",
        "warnings", "suggested_questions",
    ],
    "additionalProperties": False,
}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        # The one-line answer, before any detail. A reader who stops after the
        # first line should still have the answer to the question they asked.
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "coverage": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
        # Per-claim traceability. Each entry is one factual statement from the
        # answer together with the citation ids that support it, chosen from
        # the `available_citations` supplied in the payload — the model never
        # invents an id, a URL, or a record, and `citations.attach` drops any
        # id that is not in that catalog. Claims are additive: `summary` and
        # `key_findings` keep their existing shape, so a client that ignores
        # this field reads exactly the answer it always did.
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citation_ids": {
                        "type": "array", "items": {"type": "string"}
                    },
                },
                "required": ["text", "citation_ids"],
                "additionalProperties": False,
            },
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
        "headline", "summary", "coverage", "key_findings", "risks",
        "missing_data", "suggested_questions", "claims", "skill_results",
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

LEADER_DELEGATION_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent_key": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["agent_key", "task"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assignments"],
    "additionalProperties": False,
}

WORKER_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "workflow_keys": {"type": "array", "items": {"type": "string"}},
        "skill_keys": {"type": "array", "items": {"type": "string"}},
        "use_cached": {"type": "boolean"},
    },
    "required": ["workflow_keys", "skill_keys", "use_cached"],
    "additionalProperties": False,
}

LEADER_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent_key": {"type": "string"},
                    "question": {"type": "string"},
                    "workflow_key": {"type": ["string", "null"]},
                },
                "required": ["agent_key", "question"],
                "additionalProperties": False,
            },
        },
        "missing_data": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["done", "questions", "missing_data"],
    "additionalProperties": False,
}

WORKER_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "findings", "limitations", "evidence_ids"],
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
                    "input_value": {"type": "string"},
                    "summary_prompt": {"type": "string"},
                },
                "required": [
                    "key", "name", "package_version_id", "depends_on",
                    "input_source", "input_field", "input_value",
                    "summary_prompt",
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

# One question per turn, and it carries its own recommended answer. Several
# questions at once is bewildering to answer, and a question without a
# recommendation makes the FDE do the thinking the agent should have done.
#
# `options` are that same recommendation offered as concrete answers to click.
# The first one is the recommendation itself, so accepting the agent's pick and
# choosing an alternative are the same gesture rather than two different ones.
# They are a shortcut, never a menu: free text stays available on every turn,
# and the model is told to leave `options` empty when the real answers are not
# enumerable.
_PLAN_QUESTION_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "question": {"type": "string"},
        "recommendation": {"type": "string"},
        "why": {"type": "string"},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # What the FDE reads on the button.
                    "label": {"type": "string"},
                    # Sent as their answer when they click it. Usually a fuller
                    # sentence than the label, so the interview reads back as a
                    # conversation rather than a form.
                    "answer": {"type": "string"},
                },
                "required": ["label", "answer"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["question", "recommendation", "why", "options"],
    "additionalProperties": False,
}

_PLAN_CHAT_BASE_PROPERTIES = {
    "reply": {"type": "string"},
    "question": _PLAN_QUESTION_SCHEMA,
    "resolved": {"type": "array", "items": {"type": "string"}},
    "open_points": {"type": "array", "items": {"type": "string"}},
    "awaiting_confirmation": {"type": "boolean"},
    "ready": {"type": "boolean"},
}

_PLAN_CHAT_BASE_REQUIRED = [
    "reply", "question", "resolved", "open_points",
    "awaiting_confirmation", "ready",
]

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
                # The rest of the save form. The interview used to stop at the
                # eight fields above, which left `example_input`/
                # `example_output` empty — and the planner reads
                # `example_output` to wire a later step's `input_field`.
                "package_key": {"type": "string"},
                "query_name": {"type": "string"},
                "agent_enabled": {"type": "boolean"},
                "output_schema": {"type": "string"},
                "example_input": {"type": "string"},
                "example_output": {"type": "string"},
            },
            "required": [
                "name", "package_id", "input_cube_name",
                "input_cube_parameter", "output_cube_name", "input_mode",
                "description", "agent_instructions",
                "package_key", "query_name", "agent_enabled",
                "output_schema", "example_input", "example_output",
            ],
            "additionalProperties": False,
        },
    ),
    "required": _PLAN_CHAT_BASE_REQUIRED + ["needs_inspection", "draft"],
    "additionalProperties": False,
}

WORKFLOW_PLAN_CHAT_SCHEMA = {
    "type": "object",
    "properties": dict(
        _PLAN_CHAT_BASE_PROPERTIES,
        draft=WORKFLOW_PLAN_SCHEMA,
    ),
    "required": _PLAN_CHAT_BASE_REQUIRED + ["draft"],
    "additionalProperties": False,
}

SKILL_PLAN_CHAT_SCHEMA = {
    "type": "object",
    "properties": dict(
        _PLAN_CHAT_BASE_PROPERTIES,
        draft={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "content": {"type": "string"},
                "user_selectable": {"type": "boolean"},
                "agent_enabled": {"type": "boolean"},
            },
            "required": [
                "name", "description", "content",
                "user_selectable", "agent_enabled",
            ],
            "additionalProperties": False,
        },
    ),
    "required": _PLAN_CHAT_BASE_REQUIRED + ["draft"],
    "additionalProperties": False,
}

SPECIALIST_PLAN_CHAT_SCHEMA = {
    "type": "object",
    "properties": dict(
        _PLAN_CHAT_BASE_PROPERTIES,
        draft={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "content": {"type": "string"},
                "agent_enabled": {"type": "boolean"},
                "workflow_keys": {
                    "type": "array", "items": {"type": "string"},
                },
                "skill_keys": {
                    "type": "array", "items": {"type": "string"},
                },
            },
            "required": [
                "name", "description", "content", "agent_enabled",
                "workflow_keys", "skill_keys",
            ],
            "additionalProperties": False,
        },
    ),
    "required": _PLAN_CHAT_BASE_REQUIRED + ["draft"],
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
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        # A `clarify` used to return bare text plus every workflow name, which
        # asked the user to pick from a catalog they did not write. These let
        # the same router call ask one answerable question instead: what it
        # would choose, and the two-to-four real alternatives. Both stay
        # optional — a router that cannot enumerate honest options sends none
        # rather than inventing them, and free text is always available.
        "recommendation": {"type": ["string", "null"]},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # The button caption.
                    "label": {"type": "string"},
                    # Sent verbatim as the user's next question, so it has to
                    # be a whole question rather than the caption again.
                    "answer": {"type": "string"},
                },
                "required": ["label", "answer"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "action", "workflow_key", "tool_version_id", "clarification"
    ],
    "additionalProperties": False,
}


REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        # The follow-up restated so it stands on its own, with pronouns and
        # elisions resolved against the thread. The router and every summary
        # prompt below it see one question and no history, so a question that
        # only makes sense as a reply cannot be routed at all.
        "question": {"type": "string"},
        # Whether resolving the thread actually changed anything. A question
        # already standalone is passed through, which is checkable rather
        # than inferred from comparing two strings.
        "changed": {"type": "boolean"},
    },
    "required": ["question", "changed"],
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
