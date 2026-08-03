"""Follow-up routing and cached-evidence handling."""

import json
from typing import List

from app.common.errors import AgentError
from app.bl.workflow_engine_pkg import history
from app.bl.workflow_engine_pkg.schemas import ROUTER_SCHEMA


def follow_up(service, run, conversation, progress) -> dict:
    """Answer a follow-up in the context of the thread it belongs to.

    The question is resolved against prior turns before anything selects on
    it, so routing, execution, and synthesis all see a question that names
    its own subject. `run["question"]` keeps the user's original wording;
    only what the model reads downstream is the resolved form.
    """
    prior, workflows, tools = _available(service, conversation)
    skills = _skills(service, run)
    turns = history.recent_turns(service, conversation)
    question = history.standalone_question(service, run["question"], turns)
    selected = service._select_detail(
        question, workflows, prior, tools=tools, turns=turns
    )
    if selected.get("clarification"):
        return _clarification_result(selected, workflows, tools)
    chosen = _chosen_workflows(service, selected, workflows, tools)
    if chosen:
        return service._execute(
            run, conversation["root_id"], question, chosen, progress,
            skills, conversation.get("boundaries"),
        )
    return service._synthesize_cached(question, prior, skills)


def _available(service, conversation):
    prior = [
        item for run in conversation.get("runs", [])
        if run.get("status") in ("completed", "partial")
        for item in service._repository.run_evidence(run["id"])
    ]
    workflows = service._repository.published_workflows(["detail", "both"])
    return prior, workflows, service._repository.agent_tools()


def _skills(service, run):
    keys = run.get("skill_keys", [])
    return service._repository.published_summary_skills(keys) if keys else []


def _clarification_result(selected, workflows, tools) -> dict:
    return {
        "summary": selected["clarification"],
        "key_findings": [], "risks": [], "missing_data": [],
        "suggested_questions": [item["name"] for item in workflows + tools],
        "skill_results": [], "sections": [], "partial": False,
        "needs_clarification": True,
    }


def _chosen_workflows(service, selected, workflows, tools) -> List[dict]:
    chosen = [
        item for item in workflows
        if item["workflow_key"] == selected.get("workflow_key")
    ]
    tool = next((
        item for item in tools
        if item["id"] == selected.get("tool_version_id")
    ), None)
    return [service._tool_workflow(tool)] if tool else chosen


def select_detail(
    service, question, workflows, evidence, tools=None, turns=None
) -> dict:
    tools = tools or []
    if not workflows and not tools:
        return _no_options(evidence)
    payload = _router_payload(question, workflows, tools, evidence, turns)
    prompt = service._repository.published_content(
        "tool-aware-router",
        "בחר ראיות קיימות, workflow, טול עצמאי או clarification.",
    )
    try:
        selected = service._llm.complete_json(
            prompt, json.dumps(payload, ensure_ascii=False), ROUTER_SCHEMA
        )
        return _validate_selection(selected, workflows, tools, evidence)
    except AgentError:
        return _fallback_selection(workflows, tools, evidence)


def _no_options(evidence) -> dict:
    if evidence:
        return {"action": "use_cached", "workflow_key": None}
    return _clarify("אין עדיין תהליך מפורסם שיכול לענות על השאלה.")


def _router_payload(question, workflows, tools, evidence, turns=None) -> dict:
    """What the router selects on.

    `history` is what separates "run this workflow again" from "the user is
    asking about something already answered". Omitted entirely when empty so
    an opening request sends the payload it always did.
    """
    payload = {
        "question": question,
        "available_workflows": [_workflow_option(item) for item in workflows],
        "available_tools": [_tool_option(item) for item in tools],
        "existing_evidence": _evidence_summary(evidence),
    }
    if turns:
        payload["history"] = turns
    return payload


def _workflow_option(item: dict) -> dict:
    return {
        "workflow_key": item["workflow_key"],
        "name": item["name"],
        "description": item["description"],
    }


def _tool_option(item: dict) -> dict:
    return {
        "tool_version_id": item["id"],
        "name": item["name"],
        "description": item.get("description", ""),
        "agent_instructions": item.get("agent_instructions", ""),
    }


def _evidence_summary(evidence: List[dict]) -> List[dict]:
    from app.bl.workflow_engine_pkg.execution import chunk_facts
    grouped = {}
    for item in evidence:
        grouped.setdefault(item["step_key"], []).extend(item["records"])
    return chunk_facts(grouped)[:20]


def _validate_selection(selected, workflows, tools, evidence) -> dict:
    action = selected.get("action")
    workflow_keys = {item["workflow_key"] for item in workflows}
    tool_ids = {item["id"] for item in tools}
    if action == "workflow" and selected.get("workflow_key") not in workflow_keys:
        return _clarify()
    if action == "tool" and selected.get("tool_version_id") not in tool_ids:
        return _clarify()
    if action == "use_cached" and not evidence:
        return _single_selection(workflows, tools)
    return selected


def _fallback_selection(workflows, tools, evidence) -> dict:
    if evidence:
        return {"action": "use_cached", "workflow_key": None}
    return _single_selection(workflows, tools)


def _single_selection(workflows, tools) -> dict:
    if len(workflows) + len(tools) != 1:
        return _clarify()
    if workflows:
        return {
            "action": "workflow",
            "workflow_key": workflows[0]["workflow_key"],
        }
    return {
        "action": "tool",
        "workflow_key": None,
        "tool_version_id": tools[0]["id"],
    }


def _clarify(message="לאיזה נושא תרצו להעמיק?") -> dict:
    return {
        "action": "clarify",
        "workflow_key": None,
        "tool_version_id": None,
        "clarification": message,
    }


def tool_workflow(tool: dict) -> dict:
    instructions = (
        tool.get("agent_instructions") or tool.get("description")
        or "סכם בעברית רק את עובדות הטול."
    )
    return {
        "id": "tool:" + tool["id"],
        "workflow_key": "tool:" + tool["package_key"],
        "name": tool["name"],
        "description": tool.get("description", ""),
        "system_prompt": instructions,
        "output_schema": {},
        "steps": [_tool_step(tool, instructions)],
    }


def _tool_step(tool: dict, instructions: str) -> dict:
    return {
        "key": "tool", "name": tool["name"],
        "package_version_id": tool["id"], "depends_on": [],
        "input_source": "workflow.id", "input_field": "",
        "summary_prompt": instructions,
    }


def synthesize_cached(service, question, evidence, skills=None) -> dict:
    grouped = {}
    for item in evidence:
        grouped.setdefault(item["step_key"], []).extend(item["records"])
    facts = service._chunk_facts(grouped)
    generated = service._section_summary(
        {"name": "ראיות קיימות", "system_prompt": ""}, facts, []
    )
    return service._final_summary(
        "", question, [_cached_section(generated)], skills or []
    )


def _cached_section(generated: dict) -> dict:
    return {
        "workflow_id": "cached",
        "workflow_key": "cached-evidence",
        "name": "ראיות קיימות",
        "status": "completed",
        "summary": generated["summary"],
        "facts": generated["facts"],
        "warnings": generated["warnings"],
        "suggested_questions": generated["suggested_questions"],
        "evidence_ids": [],
    }
