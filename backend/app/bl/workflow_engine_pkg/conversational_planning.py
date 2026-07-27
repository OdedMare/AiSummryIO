"""Multi-turn FDE planning for one tool or one workflow.

``planning.py`` answers a single prompt with a single draft. Here the agent
interviews the FDE instead: one question per turn, each carrying a recommended
answer, until both sides agree the plan holds. Every turn returns the draft so
far, so the form fills in as the interview proceeds.

The interview never acts on its own conclusion. A turn that still asks
something — or that is presenting its summary for approval — is not ready, and
``is_ready`` enforces that here rather than trusting the prompt to.

The conversation is stateless. The caller replays the whole history on each
turn, which keeps the server free of session storage and matches how
``plan_workflow`` already works.

``_Planner`` owns what both planners share — bounding the history, calling the
model, normalizing the reply. Each subclass adds only the part that differs:
what context it gathers and how it turns one answer into a draft. Freedom is
added to the *wording*, never to what can be built: a workflow draft leaves
here only through ``validated_plan``, the same gate the one-shot planner uses.
"""

import json
from typing import Any, Dict, List, Optional

from app.common.errors import AgentError
from app.bl.workflow_engine_pkg.planning import tool_catalog, validated_plan
from app.bl.workflow_engine_pkg.schemas import (
    TOOL_PLAN_CHAT_SCHEMA, WORKFLOW_PLAN_CHAT_SCHEMA,
)
from app.bl.workflow_engine_pkg.planning_prompts import (
    TOOL_SYSTEM, WORKFLOW_SYSTEM,
)

_MAX_MESSAGES = 40
_MAX_MESSAGE_CHARS = 4000
_MAX_SAMPLE_ROWS = 10
_MAX_SAMPLE_FIELDS = 20
_MAX_VALUE_CHARS = 200


def plan_tool_chat(
    service, messages: List[dict], draft: Optional[dict],
    inspection: Optional[dict],
) -> dict:
    """One turn of tool planning, optionally carrying Fetch 1 ID results."""
    return _ToolPlanner(service).turn(messages, draft, inspection)


def plan_workflow_chat(
    service, messages: List[dict], draft: Optional[dict],
) -> dict:
    """One turn of workflow planning, validated like any other plan."""
    return _WorkflowPlanner(service).turn(messages, draft)


class _Planner:
    """One conversational planning turn, shared across planner kinds."""

    system = ""
    schema: Dict[str, Any] = {}

    def __init__(self, service):
        self._service = service

    def turn(self, messages, draft, *extra) -> dict:
        """Gather context, ask the model once, and shape the answer."""
        early = self._before(*extra)
        if early is not None:
            return early
        payload = self._payload(messages, draft, *extra)
        answer = self._ask(payload)
        return self._result(answer, draft)

    def _before(self, *_extra) -> Optional[dict]:
        """An answer that needs no model call, or None to continue."""
        return None

    def _payload(self, messages, draft, *_extra) -> dict:
        return {
            "conversation": self._history(messages),
            "draft_so_far": as_dict(draft),
        }

    def _ask(self, payload: dict) -> dict:
        if self._service._llm is None:
            raise AgentError("לא הוגדר חיבור למודל")
        answer = self._service._llm.complete_json(
            self.system, json.dumps(payload, ensure_ascii=False), self.schema,
        )
        return answer if isinstance(answer, dict) else {}

    def _result(self, answer: dict, draft) -> dict:
        raise NotImplementedError

    def _common(self, answer: dict) -> dict:
        question = self._question(answer.get("question"))
        return {
            "reply": bounded_text(answer.get("reply")),
            "question": question,
            "resolved": self._lines(answer.get("resolved")),
            "open_points": self._lines(answer.get("open_points")),
            # An open question means the interview is still running, whatever
            # the model claimed, so it cannot also be awaiting confirmation.
            "awaiting_confirmation":
                bool(answer.get("awaiting_confirmation")) and question is None,
        }

    @staticmethod
    def _question(value) -> Optional[dict]:
        """The single question for this turn, or None when none is asked."""
        value = as_dict(value)
        asked = bounded_text(value.get("question"))
        if not asked:
            return None
        return {
            "question": asked,
            "recommendation": bounded_text(value.get("recommendation")),
            "why": bounded_text(value.get("why")),
        }

    @staticmethod
    def _history(messages) -> List[dict]:
        """The last turns, bounded, with only the two roles the prompt names."""
        items = [
            {
                "role": "fde" if item.get("role") == "fde" else "agent",
                "text": bounded_text(item.get("text"), _MAX_MESSAGE_CHARS),
            }
            for item in (messages or []) if isinstance(item, dict)
        ]
        return [item for item in items if item["text"]][-_MAX_MESSAGES:]

    @staticmethod
    def _lines(value) -> List[str]:
        if not isinstance(value, list):
            return []
        lines = [bounded_text(item) for item in value]
        return [line for line in lines if line]


class _ToolPlanner(_Planner):
    """Fills one FLAPI tool's fields by discussing the FDE's data."""

    system = TOOL_SYSTEM
    schema = TOOL_PLAN_CHAT_SCHEMA
    _DRAFT_FIELDS = TOOL_PLAN_CHAT_SCHEMA["properties"]["draft"]["required"]
    # `agent_enabled` is the one draft field that is not text. It is merged
    # separately because "" is a meaningful "not decided yet" for every other
    # field, but would read as False here.
    _BOOL_FIELDS = ("agent_enabled",)
    # JSON arrives from the model as a string so the FDE can edit it in the
    # same textarea they always could; it is only checked for shape here.
    _JSON_FIELDS = {
        "output_schema": dict, "example_input": list, "example_output": list,
    }

    def _payload(self, messages, draft, inspection=None) -> dict:
        payload = _Planner._payload(self, messages, draft)
        if inspection:
            payload["inspection_result"] = self._inspection(inspection)
        return payload

    def _result(self, answer: dict, draft) -> dict:
        common = self._common(answer)
        return dict(
            common,
            ready=is_ready(answer, common),
            needs_inspection=bool(answer.get("needs_inspection")),
            draft=self._merged_draft(answer.get("draft"), draft),
        )

    @classmethod
    def _merged_draft(cls, draft, previous) -> Dict[str, Any]:
        """This turn over the last, so nothing agreed is silently dropped."""
        draft, previous = as_dict(draft), as_dict(previous)
        merged = {
            field: bounded_text(draft.get(field))
            or bounded_text(previous.get(field))
            for field in cls._DRAFT_FIELDS
            if field not in cls._BOOL_FIELDS
        }
        if merged["input_mode"] not in ("single", "many"):
            merged["input_mode"] = ""
        for field in cls._BOOL_FIELDS:
            value = draft.get(field, previous.get(field))
            merged[field] = True if value is None else bool(value)
        for field, kind in cls._JSON_FIELDS.items():
            merged[field] = cls._json_text(merged[field], kind)
        return merged

    @staticmethod
    def _json_text(value: str, kind: type) -> str:
        """Keep a JSON draft field only when it really parses to `kind`.

        A malformed suggestion would otherwise reach the form as text the FDE
        has to debug by hand. Dropping it back to empty leaves the field
        visibly unfilled, which the interview already knows how to resume.
        """
        if not value:
            return ""
        try:
            parsed = json.loads(value)
        except ValueError:
            return ""
        if not isinstance(parsed, kind):
            return ""
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    @staticmethod
    def _inspection(inspection: dict) -> dict:
        """Fetch 1 ID output, bounded to what the agent needs to name fields."""
        records = [
            row for row in as_dict(inspection).get("records", [])
            if isinstance(row, dict)
        ]
        fields = sorted({
            str(key) for row in records
            for key in row if not str(key).startswith("_")
        })[:_MAX_SAMPLE_FIELDS]
        return {
            "row_count": inspection.get("row_count", len(records)),
            "output_schema": inspection.get("output_schema", {}),
            "sample_data": [
                {
                    field: str(row[field])[:_MAX_VALUE_CHARS]
                    for field in fields
                    if field in row and row[field] is not None
                }
                for row in records[:_MAX_SAMPLE_ROWS]
            ],
        }


class _WorkflowPlanner(_Planner):
    """Wires catalog tools into one workflow, mapping confirmed out loud."""

    system = WORKFLOW_SYSTEM
    schema = WORKFLOW_PLAN_CHAT_SCHEMA

    def __init__(self, service):
        _Planner.__init__(self, service)
        self._tools = service._repository.list_packages()

    def _before(self, *_extra) -> Optional[dict]:
        if self._tools:
            return None
        return {
            "reply": (
                "אין עדיין טולים בקטלוג, ותהליך יכול להצביע רק על טולים "
                "קיימים. נתחיל בהגדרת טול אחד ואז נחזור לכאן."
            ),
            "question": None,
            "resolved": [],
            "open_points": ["אין טולים בקטלוג להרכיב מהם תהליך."],
            "awaiting_confirmation": False,
            "ready": False,
            "draft": validated_plan({}, []),
        }

    def _payload(self, messages, draft, *_extra) -> dict:
        return dict(
            _Planner._payload(self, messages, draft),
            available_tools=tool_catalog(self._tools),
        )

    def _result(self, answer: dict, _draft) -> dict:
        plan = validated_plan(as_dict(answer.get("draft")), self._tools)
        common = self._common(answer)
        return dict(
            common,
            # A draft the shared gate rejected is not ready however the model
            # labelled it; `rationale` already carries the reason to the FDE.
            ready=is_ready(answer, common) and plan["can_build"],
            draft=plan,
        )


def is_ready(answer: dict, common: dict) -> bool:
    """Whether a draft may be offered to the form.

    The interview does not act before the FDE confirms, so a turn that still
    asks something, or that is only now presenting its summary for approval,
    is never ready however the model labelled itself. Enforced here rather
    than trusted to the prompt: `ready` is what unlocks loading the draft.
    """
    return (
        bool(answer.get("ready"))
        and common["question"] is None
        and not common["awaiting_confirmation"]
    )


def bounded_text(value, limit: int = _MAX_MESSAGE_CHARS) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}
