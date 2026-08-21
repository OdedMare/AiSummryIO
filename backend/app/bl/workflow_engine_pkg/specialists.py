"""Bounded leader/worker orchestration over agent-enabled specialists."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.bl.workflow_engine_pkg import execution, history, routing, synthesis
from app.bl.workflow_engine_pkg.schemas import (
    LEADER_DELEGATION_SCHEMA,
    LEADER_REVIEW_SCHEMA,
    WORKER_ANSWER_SCHEMA,
    WORKER_PLAN_SCHEMA,
)
from app.common.errors import AgentError, AppError


_LEADER_FALLBACK = (
    "You lead a team of specialists. Select only supplied agents, assign one "
    "focused task to each, and never run Workflows yourself. Ask a deeper "
    "question only when material information is missing. Write every "
    "user-facing string in Hebrew."
)
_WORKER_FALLBACK = (
    "You are a specialist worker. Choose only Workflows and Skills assigned "
    "to you, use the minimum needed, and answer only from evidence you own. "
    "Write every user-facing string in Hebrew."
)

# Agentic means selective, not unlimited. These caps keep one question from
# multiplying into dozens of model and FLAPI calls. Raise them only after load
# tests show the extra breadth improves answer quality.
_MAX_SPECIALISTS = 2
_MAX_WORKFLOWS = 3


def available(service, agent_keys=None) -> List[dict]:
    """Enabled specialists when agent mode is on, otherwise none."""
    try:
        rounds = service._store.get().agent_max_rounds
    except AttributeError:
        return []
    keys = _texts(agent_keys)
    if rounds <= 0:
        if keys:
            raise ValueError("מצב הסוכנים כבוי בהגדרות")
        return []
    reader = getattr(service._repository, "enabled_specialists", None)
    if not reader:
        return []
    agents = reader(keys) if keys else reader()
    found = {item["content_key"] for item in agents}
    missing = [key for key in keys if key not in found]
    if missing:
        raise ValueError(
            "הסוכנים שנבחרו אינם זמינים: " + ", ".join(missing)
        )
    return agents


def full_summary(
    service, run, conversation, progress, agents, manually_selected=False
) -> dict:
    return _orchestrate(
        service, run, conversation, progress, agents,
        run["question"], False, [], manually_selected,
    )


def follow_up(
    service, run, conversation, progress, agents, manually_selected=False
) -> dict:
    turns = history.recent_turns(service, conversation)
    question = history.standalone_question(
        service, run["question"], turns, history.memory_context(conversation)
    )
    return _orchestrate(
        service, run, conversation, progress, agents,
        question, True, turns, manually_selected,
    )


def _orchestrate(
    service, run, conversation, progress, agents, question, is_follow_up, turns,
    manually_selected,
) -> dict:
    settings = service._store.get()
    workers = max(1, settings.max_parallel_workflows)
    routing_limit = min(_MAX_SPECIALISTS, workers)
    max_rounds = max(0, min(5, settings.agent_max_rounds))
    leader_prompt = _prompt(service, "leader-orchestrator", _LEADER_FALLBACK)
    worker_prompt = _prompt(service, "workflow-worker", _WORKER_FALLBACK)
    prior_sections, prior_sources = _prior_context(
        service, conversation, run["id"]
    )
    assignments = _delegations(
        service, question, agents, turns, leader_prompt,
        len(agents) if manually_selected else routing_limit,
        manually_selected,
    )
    states = _plan_states(
        service, assignments, prior_sections, question, is_follow_up,
        worker_prompt, workers,
    )
    workflows = _bounded_workflows(
        states, None if manually_selected else _MAX_WORKFLOWS
    )
    _emit(
        progress, 0, len(workflows), [], states, "delegating",
        max_rounds, 0,
    )
    sections = _execute_workflows(
        service, run, conversation, progress, states, workflows,
        max_rounds,
    )
    _attach_sections(states, sections)

    rounds_used = 0
    leader_missing = []
    evidence = None
    for round_number in range(1, max_rounds + 1):
        decision = _review(
            service, question, states, leader_prompt,
            len(states) if manually_selected else routing_limit,
        )
        leader_missing.extend(_texts(decision.get("missing_data")))
        questions = decision.get("questions", [])
        if decision.get("done") or not questions:
            break
        if evidence is None:
            evidence = _evidence_context(
                service, prior_sources, run["id"], sections
            )
        _answer_questions(
            service, states, questions, evidence, worker_prompt,
            round_number, workers,
        )
        rounds_used = round_number
        _emit(
            progress, len(sections), len(workflows), sections, states,
            "questioning", max_rounds, rounds_used,
        )

    final_sections = _all_sections(states)
    trace = _trace(states, "synthesizing", max_rounds, rounds_used)
    trace["missing_data"] = list(dict.fromkeys(leader_missing))
    _emit(
        progress, len(sections), len(workflows), sections, states,
        "synthesizing", max_rounds, rounds_used,
    )
    if not final_sections:
        result = execution.empty_result(
            "לא נמצא סוכן מומחה עם Workflow שיכול לענות על השאלה."
        )
    else:
        result = synthesis.final_summary(
            service, conversation.get("root_id"), question, final_sections,
            _selected_summary_skills(service, run),
            agent_context=_agent_context(states),
            leader_prompt=leader_prompt,
            # A specialist run persists evidence exactly as a direct run does,
            # so its claims are citable on the same terms. A cached section
            # carries no `evidence_ids` by design, and therefore no citation.
            evidence=execution.run_evidence(service, run),
            memory=history.memory_context(conversation),
        )
    if leader_missing:
        result["missing_data"] = list(dict.fromkeys(
            result.get("missing_data", []) + leader_missing
        ))
    result["partial"] = bool(result.get("partial") or _degraded(states))
    result["agent_trace"] = _trace(
        states, "completed", max_rounds, rounds_used
    )
    result["agent_trace"]["missing_data"] = trace["missing_data"]
    return result


def _prompt(service, key: str, fallback: str) -> str:
    reader = getattr(service._repository, "enabled_content", None)
    return reader(key, fallback) if reader else fallback


def _delegations(
    service, question, agents, turns, leader_prompt, limit,
    manually_selected=False,
) -> List[dict]:
    if manually_selected:
        return [{"agent": item, "task": question} for item in agents]
    catalog = {item["content_key"]: item for item in agents}
    payload = {
        "question": question,
        "specialists": [
            {
                "agent_key": item["content_key"],
                "name": item["name"],
                "description": item.get("description", ""),
            }
            for item in agents
        ],
    }
    if turns:
        payload["history"] = turns
    system = leader_prompt + (
        "\n\nFor this call, select the specialists relevant to the question. "
        "Return only `assignments`, each with an existing `agent_key` and "
        "one focused task written in Hebrew."
    )
    try:
        result = service._llm.complete_json(
            system, json.dumps(payload, ensure_ascii=False),
            LEADER_DELEGATION_SCHEMA,
        )
    except AgentError:
        result = {}
    assignments, seen = [], set()
    for item in result.get("assignments", []):
        key = item.get("agent_key")
        if key not in catalog or key in seen:
            continue
        task = _text(item.get("task")) or question
        assignments.append({"agent": catalog[key], "task": task})
        seen.add(key)
        if len(assignments) == limit:
            break
    if assignments:
        return assignments
    # A routing failure must fail small. Assigning every available specialist
    # here used to turn one bad model response into the most expensive path.
    return [{"agent": agents[0], "task": question}] if agents else []


def _plan_states(
    service, assignments, prior_sections, question, is_follow_up,
    worker_prompt, limit,
) -> List[dict]:
    if not assignments:
        return []
    states = []
    with ThreadPoolExecutor(max_workers=min(limit, len(assignments))) as pool:
        futures = {
            pool.submit(
                _plan_state, service, assignment, prior_sections, question,
                is_follow_up, worker_prompt,
            ): index
            for index, assignment in enumerate(assignments)
        }
        collected = {}
        for future in as_completed(futures):
            collected[futures[future]] = future.result()
        states = [collected[index] for index in range(len(assignments))]
    return states


def _plan_state(
    service, assignment, prior_sections, question, is_follow_up, worker_prompt
) -> dict:
    agent = assignment["agent"]
    config = agent.get("config") if isinstance(agent.get("config"), dict) else {}
    allowed_workflows = _texts(config.get("workflow_keys"))
    allowed_skills = _texts(config.get("skill_keys"))
    roles = (
        ["baseline", "detail", "both"] if is_follow_up
        else ["baseline", "both"]
    )
    workflows = service._repository.enabled_workflows_by_keys(
        allowed_workflows, roles
    )
    skill_options = service._repository.enabled_skill_options(allowed_skills)
    cached = [
        item for item in prior_sections
        if item.get("workflow_key") in set(allowed_workflows)
    ]
    payload = {
        "question": question,
        "delegated_task": assignment["task"],
        "workflows": [_workflow_option(item) for item in workflows],
        "skills": [_skill_option(item) for item in skill_options],
        "cached_sections": [_report_section(item) for item in cached],
    }
    system = _worker_system(agent, [], worker_prompt) + (
        "\n\nFor this call, plan your work only. Choose the minimum needed "
        "from the supplied keys. Set `use_cached=true` only when the existing "
        "sections are sufficient."
    )
    try:
        plan = service._llm.complete_json(
            system, json.dumps(payload, ensure_ascii=False), WORKER_PLAN_SCHEMA
        )
    except AgentError:
        plan = {}
    explicit = routing.explicit_workflow(question, workflows)
    workflow_keys = (
        [explicit["workflow_key"]] if explicit else
        _allowed(
            plan.get("workflow_keys"),
            [item["workflow_key"] for item in workflows],
        )
    )
    skill_keys = _allowed(
        plan.get("skill_keys"), [item["content_key"] for item in skill_options]
    )
    use_cached = bool(plan.get("use_cached") and cached)
    if not workflow_keys and not use_cached:
        if is_follow_up and cached:
            use_cached = True
        else:
            # Fail small: one safe enabled workflow is preferable to running
            # the entire catalog because planning returned no usable choice.
            workflow_keys = [workflows[0]["workflow_key"]] if workflows else []
    selected = {
        item["workflow_key"]: item for item in workflows
        if item["workflow_key"] in workflow_keys
    }
    skills = service._repository.enabled_skills(skill_keys)
    prepared = [
        _worker_workflow(
            selected[key], agent, assignment["task"], skills, worker_prompt
        )
        for key in workflow_keys if key in selected
    ]
    status = "planned" if prepared or use_cached else "failed"
    return {
        "agent": agent,
        "task": assignment["task"],
        "workflows": prepared,
        "skills": skills,
        "cached_sections": cached if use_cached else [],
        "sections": [],
        "answers": [],
        "status": status,
        "error": "" if status != "failed" else (
            "אין Workflow מפורסם מתאים או ראיות קודמות זמינות."
        ),
    }


def _bounded_workflows(states, total_limit=_MAX_WORKFLOWS) -> List[dict]:
    """Run each workflow once and share its section with its owners."""
    unique = {}
    for state in states:
        agent_key = state["agent"]["content_key"]
        bounded = []
        for workflow in state["workflows"][:_MAX_WORKFLOWS]:
            workflow_id = workflow["id"]
            selected = unique.get(workflow_id)
            if selected is None:
                if total_limit is not None and len(unique) == total_limit:
                    continue
                selected = dict(workflow)
                selected["_agent_keys"] = []
                unique[workflow_id] = selected
            if agent_key not in selected["_agent_keys"]:
                selected["_agent_keys"].append(agent_key)
            bounded.append(selected)
        state["workflows"] = bounded
    return list(unique.values())


def _worker_workflow(workflow, agent, task, skills, worker_prompt) -> dict:
    prepared = dict(workflow)
    prepared["system_prompt"] = "\n\n".join(filter(None, [
        agent.get("content", ""),
        "\n\n".join(item.get("content", "") for item in skills),
        workflow.get("system_prompt", ""),
        worker_prompt,
    ]))
    prepared["_agent_key"] = agent["content_key"]
    prepared["_agent_task"] = task
    return prepared


def _execute_workflows(
    service, run, conversation, progress, states, workflows, max_rounds
) -> List[dict]:
    if not workflows:
        return []
    owners = {
        item["id"]: item.get("_agent_keys", [item["_agent_key"]])
        for item in workflows
    }

    def report(completed, total, sections):
        arrived = {item["workflow_id"]: item for item in sections}
        for state in states:
            ids = {item["id"] for item in state["workflows"]}
            own = [arrived[item_id] for item_id in ids if item_id in arrived]
            if own:
                state["status"] = (
                    "partial" if any(item["status"] != "completed" for item in own)
                    else "running"
                )
        _emit(
            progress, completed, total, sections, states,
            "running_workflows", max_rounds, 0,
        )

    sections = execution.execute_sections(
        service, run, conversation.get("root_id"), workflows, report,
        conversation.get("boundaries"),
    )
    for section in sections:
        section["agent_keys"] = owners.get(section["workflow_id"], [])
        section["agent_key"] = (
            section["agent_keys"][0] if section["agent_keys"] else ""
        )
    return sections


def _attach_sections(states, sections) -> None:
    for state in states:
        key = state["agent"]["content_key"]
        current = [
            item for item in sections
            if key in item.get("agent_keys", [item.get("agent_key", "")])
        ]
        current_keys = {item["workflow_key"] for item in current}
        cached = [
            _cached_section(item) for item in state["cached_sections"]
            if item.get("workflow_key") not in current_keys
        ]
        state["sections"] = current + cached
        if not state["sections"]:
            state["status"] = "failed"
        elif any(item["status"] != "completed" for item in state["sections"]):
            state["status"] = "partial"
        else:
            state["status"] = "completed"


def _review(service, question, states, leader_prompt, limit) -> dict:
    payload = {"question": question, "specialist_reports": _reports(states)}
    system = leader_prompt + (
        "\n\nFor this call, decide whether the reports are sufficient. Set "
        "`done=true` when no deeper question could materially improve the "
        "answer. Otherwise return at most one question for each relevant "
        "specialist, using only a supplied `agent_key`. Write questions in "
        "Hebrew."
    )
    try:
        result = service._llm.complete_json(
            system, json.dumps(payload, ensure_ascii=False), LEADER_REVIEW_SCHEMA
        )
    except AgentError:
        return {"done": True, "questions": [], "missing_data": []}
    known = {state["agent"]["content_key"] for state in states}
    questions, seen = [], set()
    for item in result.get("questions", []):
        key = item.get("agent_key")
        question_text = _text(item.get("question"))
        if key not in known or key in seen or not question_text:
            continue
        questions.append({"agent_key": key, "question": question_text})
        seen.add(key)
        if len(questions) == limit:
            break
    return {
        "done": bool(result.get("done")),
        "questions": questions,
        "missing_data": _texts(result.get("missing_data")),
    }


def _answer_questions(
    service, states, questions, evidence, worker_prompt, round_number, limit
) -> None:
    by_key = {state["agent"]["content_key"]: state for state in states}
    with ThreadPoolExecutor(max_workers=min(limit, len(questions))) as pool:
        futures = {
            pool.submit(
                _answer, service, by_key[item["agent_key"]], item["question"],
                evidence, worker_prompt, round_number,
            ): item["agent_key"]
            for item in questions
        }
        for future in as_completed(futures):
            state = by_key[futures[future]]
            answer = future.result()
            state["answers"].append(answer)
            if answer["status"] != "completed" and state["status"] == "completed":
                state["status"] = "partial"


def _answer(
    service, state, question, evidence, worker_prompt, round_number
) -> dict:
    owned = set(_texts((state["agent"].get("config") or {}).get("workflow_keys")))
    items = [item for item in evidence if item.get("_workflow_key") in owned]
    allowed_ids = {item["id"] for item in items}
    payload = {
        "delegated_task": state["task"],
        "leader_question": question,
        "reports": [_report_section(item) for item in state["sections"]],
        "evidence": _evidence_payload(service, items),
    }
    system = _worker_system(state["agent"], state["skills"], worker_prompt) + (
        "\n\nFor this call, answer the leader's question only from the "
        "attached evidence. Every factual finding must cite at least one "
        "valid `evidence_id`. Write the answer in Hebrew."
    )
    try:
        result = service._llm.complete_json(
            system, json.dumps(payload, ensure_ascii=False), WORKER_ANSWER_SCHEMA
        )
    except AgentError as exc:
        return _failed_answer(round_number, question, str(exc))
    cited = [
        item for item in _texts(result.get("evidence_ids"))
        if item in allowed_ids
    ]
    findings = _texts(result.get("findings"))
    limitations = _texts(result.get("limitations"))
    if (findings or _text(result.get("answer"))) and not cited:
        return _failed_answer(
            round_number, question,
            "תשובת ההעמקה נדחתה משום שלא ציטטה ראיה השייכת לסוכן.",
        )
    return {
        "round": round_number,
        "question": question,
        "answer": _text(result.get("answer")),
        "findings": findings,
        "limitations": limitations,
        "evidence_ids": cited,
        "status": "completed",
    }


def _failed_answer(round_number, question, reason) -> dict:
    return {
        "round": round_number,
        "question": question,
        "answer": "לא ניתן היה להשלים את שאלת ההעמקה.",
        "findings": [],
        "limitations": [reason] if reason else [],
        "evidence_ids": [],
        "status": "failed",
    }


def _evidence_payload(service, evidence) -> List[dict]:
    policies = {}
    result = []
    for item in evidence:
        policy = _evidence_policy(
            service, item["workflow_id"], item["step_key"], policies
        )
        facts = execution.chunk_facts(
            {item["step_key"]: item.get("records", [])},
            {item["step_key"]: policy} if policy is not None else None,
        )
        result.append({
            "evidence_id": item["id"],
            "workflow_key": item.get("_workflow_key", ""),
            "step_key": item["step_key"],
            "facts": facts,
        })
    return result


def _evidence_policy(service, workflow_id, step_key, cache):
    cache_key = (workflow_id, step_key)
    if cache_key in cache:
        return cache[cache_key]
    try:
        workflow = service._repository.get_workflow(workflow_id)
        step = next(item for item in workflow["steps"] if item["key"] == step_key)
        package = service._repository.get_package(step["package_version_id"])
        cache[cache_key] = execution._summary_fields(package)
    except (AppError, AttributeError, KeyError, StopIteration):
        cache[cache_key] = None
    return cache[cache_key]


def _prior_context(service, conversation, current_run_id):
    sections, sources = [], []
    for run in conversation.get("runs", []):
        if run.get("id") == current_run_id:
            continue
        if run.get("status") not in ("completed", "partial"):
            continue
        run_sections = (run.get("result") or {}).get("sections", [])
        sections.extend(run_sections)
        sources.append((run["id"], run_sections))
    return sections, sources


def _evidence_context(service, prior_sources, current_run_id, sections):
    """Load raw evidence only if a review actually asks for deeper analysis."""
    evidence = []
    for run_id, run_sections in prior_sources:
        evidence.extend(_tag_evidence(_run_evidence(service, run_id), run_sections))
    evidence.extend(_tag_evidence(
        _run_evidence(service, current_run_id), sections
    ))
    return evidence


def _run_evidence(service, run_id) -> List[dict]:
    reader = getattr(service._repository, "run_evidence", None)
    return reader(run_id) if reader else []


def _tag_evidence(evidence, sections) -> List[dict]:
    keys = {
        item.get("workflow_id"): item.get("workflow_key", "")
        for item in sections
    }
    tagged = []
    for item in evidence:
        copy = dict(item)
        copy["_workflow_key"] = keys.get(item.get("workflow_id"), "")
        tagged.append(copy)
    return tagged


def _selected_summary_skills(service, run) -> List[dict]:
    keys = run.get("skill_keys", [])
    return service._repository.enabled_summary_skills(keys) if keys else []


def _worker_system(agent, skills, worker_prompt) -> str:
    return "\n\n".join(filter(None, [
        agent.get("content", ""),
        "\n\n".join(item.get("content", "") for item in skills),
        worker_prompt,
    ]))


def _workflow_option(item) -> dict:
    return {
        "workflow_key": item["workflow_key"],
        "name": item["name"],
        "description": item.get("description", ""),
        "role": item.get("role", ""),
    }


def _skill_option(item) -> dict:
    return {
        "skill_key": item["content_key"],
        "name": item["name"],
        "description": item.get("description", ""),
    }


def _cached_section(section) -> dict:
    copy = dict(section)
    copy["evidence_ids"] = []
    copy["cached"] = True
    return copy


def _report_section(section) -> dict:
    return {
        "workflow_key": section.get("workflow_key", ""),
        "name": section.get("name", ""),
        "status": section.get("status", ""),
        "summary": section.get("summary", ""),
        "coverage": section.get("coverage", ""),
        "facts": section.get("facts", []),
        "patterns": section.get("patterns", []),
        "outliers": section.get("outliers", []),
        "warnings": section.get("warnings", []),
    }


def _review_section(section) -> dict:
    """What the leader needs to judge sufficiency — not the data itself.

    The leader decides *whether* a follow-up question would help; it never
    writes the answer. Sending whole `facts` made this payload grow linearly
    with the rows collected and resend all of it every round, which on a
    local model truncates silently — and a truncated review returns an
    arbitrary done=true rather than an error anyone can see.

    `patterns` and `outliers` stay because they are already summaries, bounded
    in size, and they are what lets the leader notice a distribution worth
    asking about. `fact_count` answers the only question `facts` was really
    serving here: whether the section is empty or substantial.
    """
    return {
        "workflow_key": section.get("workflow_key", ""),
        "name": section.get("name", ""),
        "status": section.get("status", ""),
        "summary": section.get("summary", ""),
        "coverage": section.get("coverage", ""),
        "fact_count": len(section.get("facts", [])),
        "patterns": section.get("patterns", []),
        "outliers": section.get("outliers", []),
        "warnings": section.get("warnings", []),
    }


def _reports(states) -> List[dict]:
    """The leader's view of every specialist. Read only by `_review`."""
    return [
        {
            "agent_key": state["agent"]["content_key"],
            "name": state["agent"]["name"],
            "status": state["status"],
            "sections": [_review_section(item) for item in state["sections"]],
            "answers": [
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "findings": item["findings"],
                    "limitations": item["limitations"],
                }
                for item in state["answers"]
            ],
        }
        for state in states
    ]


def _agent_context(states) -> List[dict]:
    # Section facts are already sent separately to final synthesis. Repeating
    # them inside specialist_reports spent context on the same text twice.
    return [
        {
            "agent_key": state["agent"]["content_key"],
            "name": state["agent"]["name"],
            "task": state["task"],
            "status": state["status"],
            "answers": [
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "findings": item["findings"],
                    "limitations": item["limitations"],
                }
                for item in state["answers"]
            ],
        }
        for state in states
    ]


def _all_sections(states) -> List[dict]:
    result, seen = [], set()
    for state in states:
        for section in state["sections"]:
            key = section.get("workflow_key") or section.get("workflow_id")
            if key in seen:
                continue
            seen.add(key)
            result.append(section)
    return result


def _trace(states, phase, max_rounds, rounds_used) -> dict:
    return {
        "phase": phase,
        "max_rounds": max_rounds,
        "rounds_used": rounds_used,
        "specialists": [
            {
                "agent_id": state["agent"]["id"],
                "agent_key": state["agent"]["content_key"],
                "name": state["agent"]["name"],
                "task": state["task"],
                "status": state["status"],
                "workflow_ids": [item["id"] for item in state["workflows"]],
                "workflow_keys": [
                    item["workflow_key"] for item in state["workflows"]
                ],
                "skill_ids": [item["id"] for item in state["skills"]],
                "skill_keys": [item["content_key"] for item in state["skills"]],
                "answers": list(state["answers"]),
                "error": state["error"],
            }
            for state in states
        ],
    }


def _emit(
    progress, completed, total, sections, states, phase, max_rounds, rounds_used
) -> None:
    progress(
        completed, total, sections,
        _trace(states, phase, max_rounds, rounds_used), phase,
    )


def _degraded(states) -> bool:
    return any(
        state["status"] != "completed"
        or any(answer["status"] != "completed" for answer in state["answers"])
        for state in states
    )


def _allowed(selected, allowed) -> List[str]:
    allowed_set = set(allowed)
    return [item for item in _texts(selected) if item in allowed_set]


def _texts(value) -> List[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(
        item.strip() for item in value
        if isinstance(item, str) and item.strip()
    ))


def _text(value) -> str:
    return value.strip()[:2000] if isinstance(value, str) else ""
