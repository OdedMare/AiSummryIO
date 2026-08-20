"""Follow-up routing and cached-evidence handling."""

import json
from typing import List

from app.common.errors import AgentError
from app.bl.workflow_engine_pkg import citation_context, history
from app.bl.workflow_engine_pkg.schemas import ROUTER_SCHEMA


def follow_up(service, run, conversation, progress, project=None) -> dict:
    """Answer a follow-up in the context of the thread it belongs to.

    The question is resolved against prior turns before anything selects on
    it, so routing, execution, and synthesis all see a question that names
    its own subject. `run["question"]` keeps the user's original wording;
    only what the model reads downstream is the resolved form.
    """
    cited = _cited_answer(service, run, conversation)
    if cited is not None:
        return cited
    prior, workflows, tools = _available(service, conversation, project)
    skills = service._project_skills(run, project)
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


def _cited_answer(service, run, conversation):
    """The answer to a follow-up that is about an already-cited record.

    Returns None for an ordinary follow-up, so the routing below is untouched
    for every question that does not reference a citation.

    An explicit `citation_id` wins outright: the user asked while looking at
    that source, so there is nothing to infer and nothing to search. Only
    without one is the question matched against the thread's citations, and
    only a clear match answers — an ambiguous one asks which record was meant
    rather than showing the wrong one.
    """
    resolved = citation_context.resolve_explicit(service, conversation, run)
    if resolved:
        return citation_context.record_answer(run["question"], resolved)
    if citation_context.explicit_ids(run):
        # The request named ids, but none of them exist in this thread. Fall
        # through to ordinary routing rather than inventing a record.
        return None
    match = citation_context.match_thread(service, conversation, run["question"])
    if match.get("ambiguous"):
        return citation_context.clarification(match["ambiguous"])
    if match.get("citation"):
        return citation_context.record_answer(
            run["question"], [match["citation"]]
        )
    return None


def _available(service, conversation, project=None):
    prior = [
        item for run in conversation.get("runs", [])
        if run.get("status") in ("completed", "partial")
        for item in service._repository.run_evidence(run["id"])
    ]
    if project:
        workflows = service._repository.enabled_workflows_by_keys(
            project.get("workflow_keys", []), ["detail", "both"]
        )
        tools = service._repository.agent_tools_by_keys(
            project.get("tool_keys", [])
        )
        return prior, workflows, tools
    workflows = service._repository.enabled_workflows(["detail", "both"])
    return prior, workflows, service._repository.agent_tools()


def _clarification_result(selected, workflows, tools) -> dict:
    """The agent asking one question back, rather than listing its catalog.

    `suggested_questions` used to be every workflow and tool name, which asked
    the user to choose from an inventory they did not write and could not
    interpret. Options are real answers to the question actually asked; when
    the router could not name any, the names remain as the honest fallback —
    something to click beats a dead end.
    """
    options = _clarify_options(selected)
    return {
        "summary": selected["clarification"],
        "key_findings": [], "risks": [], "missing_data": [],
        "suggested_questions": (
            [option["answer"] for option in options]
            or [item["name"] for item in workflows + tools]
        ),
        "skill_results": [], "sections": [], "partial": False,
        "needs_clarification": True,
        "recommendation": _text(selected.get("recommendation")),
        "options": options,
    }


# Past four the user is reading a list instead of choosing, which is the
# deliberation the options exist to save. Mirrors the FDE interview's bound.
_MAX_OPTIONS = 4
_MAX_OPTION_CHARS = 120
_MAX_ANSWER_CHARS = 400


def _clarify_options(selected: dict) -> List[dict]:
    """Clickable answers, bounded and deduplicated.

    A clicked option is sent verbatim as the user's next question, so one
    missing its `answer` has nothing to send and is dropped rather than
    falling back to the label — a caption in the composer is a fragment where
    a question belongs. One option is not a choice, so a lone survivor goes
    too: the question itself already says the same thing.
    """
    offered = selected.get("options")
    if not isinstance(offered, list):
        return []
    options, seen = [], set()
    for item in offered:
        if not isinstance(item, dict):
            continue
        label = _text(item.get("label"), _MAX_OPTION_CHARS)
        answer = _text(item.get("answer"), _MAX_ANSWER_CHARS)
        if not label or not answer or label in seen:
            continue
        seen.add(label)
        options.append({"label": label, "answer": answer})
        if len(options) == _MAX_OPTIONS:
            break
    return options if len(options) > 1 else []


def _text(value, limit: int = _MAX_ANSWER_CHARS) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


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
    ratings = _route_ratings(service)
    payload = _router_payload(question, workflows, tools, evidence, turns, ratings)
    prompt = service._repository.enabled_content(
        "tool-aware-router",
        "Choose existing evidence, a Workflow, an approved standalone tool, "
        "or clarification. Write any user-facing text in Hebrew.",
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
    return _clarify("אין עדיין תהליך פעיל שיכול לענות על השאלה.")


def _route_ratings(service) -> dict:
    """Per-route star ratings, or empty when the repository predates them.

    Mirrors `history.recent_turns`: reached through `getattr` so a fake or
    older repository without `route_ratings` degrades to no signal rather
    than crashing routing.
    """
    reader = getattr(service._repository, "route_ratings", None)
    return reader() if reader else {}


def _router_payload(
    question, workflows, tools, evidence, turns=None, ratings=None
) -> dict:
    """What the router selects on.

    `history` is what separates "run this workflow again" from "the user is
    asking about something already answered". Omitted entirely when empty so
    an opening request sends the payload it always did.
    """
    ratings = ratings or {}
    payload = {
        "question": question,
        "available_workflows": [
            _workflow_option(item, ratings) for item in workflows
        ],
        "available_tools": [_tool_option(item, ratings) for item in tools],
        "existing_evidence": _evidence_summary(evidence),
    }
    if turns:
        payload["history"] = turns
    return payload


def _workflow_option(item: dict, ratings: dict) -> dict:
    option = {
        "workflow_key": item["workflow_key"],
        "name": item["name"],
        "description": item["description"],
    }
    option.update(_rating_fields(ratings.get(item.get("id"))))
    return option


def _tool_option(item: dict, ratings: dict) -> dict:
    option = {
        "tool_version_id": item["id"],
        "name": item["name"],
        "description": item.get("description", ""),
        "agent_instructions": item.get("agent_instructions", ""),
    }
    option.update(_rating_fields(ratings.get("tool:" + item["id"])))
    return option


def _rating_fields(row) -> dict:
    """`avg_rating`/`rating_count`, present only behind real feedback.

    Omitted rather than defaulted to a neutral score: a route no one has
    rated yet is unproven, not average, and the router prompt is told to
    read a missing rating that way.
    """
    if not row or not row.get("rating_count"):
        return {}
    return {
        "avg_rating": float(row["avg_rating"]),
        "rating_count": int(row["rating_count"]),
    }


def _evidence_summary(evidence: List[dict]) -> List[dict]:
    from app.bl.workflow_engine_pkg.execution import chunk_facts
    grouped = {}
    for item in evidence:
        grouped.setdefault(item["step_key"], []).extend(item["records"])
    return chunk_facts(grouped)[:20]


def _validate_selection(selected, workflows, tools, evidence) -> dict:
    """The router's choice, or a clarify when it named something unavailable.

    A rejected selection is a dead end unless the user is given somewhere to
    go, so these clarifies carry the options the router should have chosen
    from — the one case where the real alternatives are known exactly.
    """
    action = selected.get("action")
    workflow_keys = {item["workflow_key"] for item in workflows}
    tool_ids = {item["id"] for item in tools}
    if action == "workflow" and selected.get("workflow_key") not in workflow_keys:
        return _clarify(options=_catalog_options(workflows, tools))
    if action == "tool" and selected.get("tool_version_id") not in tool_ids:
        return _clarify(options=_catalog_options(workflows, tools))
    if action == "use_cached" and not evidence:
        return _single_selection(workflows, tools)
    return selected


def _catalog_options(workflows, tools) -> List[dict]:
    """Each available route as a clickable question.

    The label is the route's name; the answer is a question phrased as the
    user would ask it, since a clicked option is sent verbatim as their next
    message and the name alone would arrive as a fragment.
    """
    return [
        {"label": item["name"], "answer": "ספר לי על " + item["name"]}
        for item in list(workflows) + list(tools)
    ][:_MAX_OPTIONS]


def _fallback_selection(workflows, tools, evidence) -> dict:
    if evidence:
        return {"action": "use_cached", "workflow_key": None}
    return _single_selection(workflows, tools)


def _single_selection(workflows, tools) -> dict:
    """The only available route, or a clarify offering the several there are.

    This is the fallback when the model is unavailable, so the options are
    built in Python from the catalog rather than asked for — the one path
    that has to work with no model at all.
    """
    if len(workflows) + len(tools) != 1:
        return _clarify(options=_catalog_options(workflows, tools))
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


def _clarify(message="לאיזה נושא תרצו להעמיק?", options=None) -> dict:
    return {
        "action": "clarify",
        "workflow_key": None,
        "tool_version_id": None,
        "clarification": message,
        "recommendation": "",
        "options": options or [],
    }


def tool_workflow(tool: dict) -> dict:
    instructions = (
        tool.get("agent_instructions") or tool.get("description")
        or "Summarize only the tool's facts. Write the result in Hebrew."
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
