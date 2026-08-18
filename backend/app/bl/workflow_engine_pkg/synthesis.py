"""LLM-backed section, final-summary, and Skill synthesis."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from app.common.errors import AgentError
from app.common.logging_setup import trace
from app.bl.workflow_engine_pkg.schemas import (
    FINAL_SCHEMA, SECTION_SCHEMA, SKILL_SCHEMA, merge_output_schema,
)

_log = trace("synthesis")


# A reducer never receives more than this many prior analyses in one call.
_REDUCE_BATCH_SIZE = 12

# Appended to the workflow's own prompt rather than replacing it: an FDE writes
# domain instructions, and these describe the data's shape for every workflow.
_TABULAR_GUIDANCE = """
Data shape: `row_count` is the total number of records for the step. In a
single batch, `rows` contains every record. For a large result, each batch is
analyzed separately and all batch analyses are merged before the answer is
returned. `stats` is computed in code across all records:
`present`/`missing`, `distinct`, `counts`
(frequencies for fields with up to 15 values), and `min`/`max`/`mean` for
numeric fields.

Reading rules:
1. Open with scope: how many rows and which steps. State this explicitly in
   `coverage`.
2. Prefer a distribution over an example. "263 of 412 are open" is a
   finding; a single row is not.
3. Use the numbers in `stats` exactly as given. Do not count `rows` yourself.
   Do not calculate a percentage without a denominator.
4. A high `missing` value for a field is a coverage finding; state it.
5. Outliers matter more than typical values: a future date, a close before an
   open, a duplicate, or an extreme value.

Output allocation:
- `facts`: concrete findings about rows or entities.
- `patterns`: distributions, time ranges, and concentrations.
- `outliers`: exceptional records only; empty when there are none.
- `coverage`: what was collected and included, in one sentence.

Do not enumerate rows one by one, present a field name as a finding, state a
count absent from `stats`, infer causality, or treat `row_count` as a count of
unique entities. Write every user-facing output string in Hebrew.
"""

_MAP_GUIDANCE = """

The current input is one batch from a large result. `rows` contains every row
in this batch and is not a sample. Analyze every row and return concise facts,
patterns, and outliers in Hebrew. Do not extrapolate batch counts to the whole
dataset; merging happens in the next stage.
"""

_REDUCE_GUIDANCE = """

`chunk_analyses` contains analyses of separate, non-overlapping batches that
together cover every record. Merge them all. Do not omit a unique finding or
outlier because it appeared in only one batch. Take counts and ranges only
from `whole_dataset.stats`, which is computed across the full dataset. Return
all user-facing text in Hebrew.
"""


def section_summary(service, workflow, facts, warnings) -> dict:
    base_system = workflow.get("system_prompt") or (
        "Summarize the workflow facts in Hebrew. Do not add information "
        "that is not present."
    )
    schema = merge_output_schema(workflow.get("output_schema"))
    try:
        if len(facts) > 1 and all(
            item.get("complete_rows") for item in facts
        ):
            analyses = _map_fact_chunks(service, workflow, facts, base_system)
            while len(analyses) > _REDUCE_BATCH_SIZE:
                analyses = _reduce_round(
                    service, workflow, facts, analyses, base_system
                )
            return _reduce_section(
                service, workflow, facts, analyses, warnings,
                base_system, schema,
            )
        payload = _payload(workflow, facts=facts, warnings=warnings)
        return _section_result(service._llm.complete_json(
            base_system + _TABULAR_GUIDANCE,
            json.dumps(payload, ensure_ascii=False), schema,
        ))
    except AgentError as exc:
        _log.warning(
            "section synthesis degraded workflow=%s: %s",
            workflow.get("workflow_key", workflow.get("name", "unknown")),
            exc,
        )
        return _section_fallback(workflow, facts, str(exc))


def _map_fact_chunks(service, workflow, facts, base_system) -> List[dict]:
    results = [None] * len(facts)
    with ThreadPoolExecutor(
        max_workers=_section_workers(service, len(facts))
    ) as pool:
        futures = {
            pool.submit(
                _map_fact_chunk, service, workflow, fact, base_system
            ): index
            for index, fact in enumerate(facts)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


def _map_fact_chunk(service, workflow, fact, base_system) -> dict:
    result = service._llm.complete_json(
        base_system + _MAP_GUIDANCE,
        json.dumps(_payload(workflow, fact_chunk=fact), ensure_ascii=False),
        SECTION_SCHEMA,
    )
    return _section_result(result)


def _reduce_round(service, workflow, facts, analyses, base_system) -> List[dict]:
    reduced = []
    for index in range(0, len(analyses), _REDUCE_BATCH_SIZE):
        group = analyses[index:index + _REDUCE_BATCH_SIZE]
        reduced.append(
            group[0] if len(group) == 1 else _reduce_section(
                service, workflow, facts, group, [],
                base_system, SECTION_SCHEMA,
            )
        )
    return reduced


def _reduce_section(
    service, workflow, facts, analyses, warnings, base_system, schema
) -> dict:
    payload = _payload(
        workflow,
        whole_dataset=_dataset_facts(facts),
        chunk_analyses=analyses,
        warnings=warnings,
    )
    result = service._llm.complete_json(
        base_system + _TABULAR_GUIDANCE + _REDUCE_GUIDANCE,
        json.dumps(payload, ensure_ascii=False), schema,
    )
    return _section_result(result)


def _payload(workflow, **values) -> dict:
    payload = {"workflow": workflow["name"], **values}
    if workflow.get("_agent_task"):
        payload["delegated_task"] = workflow["_agent_task"]
    return payload


def _dataset_facts(facts: List[dict]) -> List[dict]:
    datasets, seen = [], set()
    for fact in facts:
        step = fact.get("step")
        if step in seen:
            continue
        seen.add(step)
        datasets.append({
            key: fact[key] for key in (
                "step", "row_count", "fields", "stats", "samples",
                "summary_instruction",
            ) if key in fact
        })
    return datasets


def _section_workers(service, count: int) -> int:
    try:
        limit = service._store.get().max_parallel_workflows
    except AttributeError:
        limit = 1
    return max(1, min(limit, count))


def _section_result(result: dict) -> dict:
    contract = set(SECTION_SCHEMA["properties"])
    return {
        "summary": str(result.get("summary", "")),
        "coverage": str(result.get("coverage", "")),
        "facts": list(result.get("facts", [])),
        "patterns": list(result.get("patterns", [])),
        "outliers": list(result.get("outliers", [])),
        "warnings": list(result.get("warnings", [])),
        "suggested_questions": list(result.get("suggested_questions", [])),
        "fields": {key: value for key, value in result.items()
                   if key not in contract},
    }


def _section_fallback(
    workflow: dict, facts: List[dict], reason: str = ""
) -> dict:
    """Stated coverage, and `degraded` so the caller can say the model failed.

    Without the flag a reader cannot tell a thin section from a fallback, and
    reads "no information" where the truth is "the model did not answer".
    """
    datasets = _dataset_facts(facts)
    count = sum(item["row_count"] for item in datasets)
    return {
        "summary": "נאספו %d רשומות בתהליך %s." % (count, workflow["name"]),
        "coverage": "%d רשומות ב-%d שלבים" % (count, len(datasets)),
        "facts": ["%s: %d רשומות" % (item["step"], item["row_count"])
                  for item in datasets],
        "patterns": [],
        "outliers": [],
        "warnings": [
            "הסיכום הופק ללא מודל השפה; מוצגות ספירות בלבד"
            + (": " + reason if reason else ".")
        ],
        "suggested_questions": [],
        "fields": {},
        "degraded": True,
    }


def final_summary(
    service, root_id, question, sections, skills=None,
    agent_context=None, leader_prompt="",
) -> dict:
    skills = skills or []
    safe_sections = [_safe_section(section) for section in sections]
    final = _shared_summary(
        service, question, sections, safe_sections,
        agent_context or [], leader_prompt,
    )
    final["skill_results"] = service._run_skills(
        question, skills, sections, safe_sections
    )
    final["sections"] = sections
    final["partial"] = any(item["status"] != "completed" for item in sections)
    return final


def _safe_section(section: dict) -> dict:
    """The section view sent to the final call and to every Skill.

    `patterns`, `outliers`, and `coverage` are included because a Skill that
    never sees rows can only reason about distributions if the section carries
    them. Optional via `get`, so a section built before this contract — a
    cached run, a `preview_skill` sample — still passes through.
    """
    keys = (
        "workflow_key", "name", "status", "summary", "facts", "warnings"
    )
    safe = {key: section[key] for key in keys}
    for key in ("coverage", "patterns", "outliers"):
        if section.get(key):
            safe[key] = section[key]
    return safe


def _shared_summary(
    service, question, sections, safe_sections,
    agent_context=None, leader_prompt="",
) -> dict:
    prompt = service._repository.enabled_content(
        "final-summary",
        "Summarize only from the supplied facts, write every user-facing "
        "string in Hebrew, and return JSON.",
    )
    if leader_prompt:
        prompt = leader_prompt + "\n\n" + prompt
    prompt += (
        "\nReturn `skill_results` as an empty array. Each Skill runs in a "
        "separate call."
        "\n`headline` is one sentence that answers the question; a reader "
        "who sees only it still gets the answer. Do not open by describing "
        "the process or what was searched."
        "\n`coverage` summarizes in one sentence how much data supports the "
        "answer, using the sections' `coverage` fields. Do not imply full "
        "coverage when a section failed."
        "\nRank `key_findings` by impact on a decision, not section order. "
        "Merge overlapping findings and do not repeat a finding."
        "\nUse the sections' `patterns` and `outliers`: include a broad "
        "distribution in `key_findings` only when it changes the conclusion, "
        "and put an outlier in `risks`. Write all output text in Hebrew."
        "\nFor rating, ranking, and comparison questions:\n"
        "- Distinguish relative ordering of several items from scoring one "
        "item on several dimensions. Follow the form the user requested.\n"
        "- Preserve the exact minimum, maximum, direction, criteria, and "
        "scope, including scales written in words. Never replace 1-4 with "
        "1-5. If no numeric scale was requested, rank without inventing one.\n"
        "- Score separate dimensions separately (for example beauty and "
        "tourist appeal); do not merge or average them unless asked. Apply "
        "one consistent rubric across items, sort highest-to-lowest unless "
        "asked otherwise, and preserve honest ties.\n"
        "- Put every result in `key_findings` as `name or dimension — "
        "score/maximum or rank — short evidence-based reason`. State the "
        "observable indicators behind the judgment.\n"
        "- Never turn missing evidence into a low score or invent support for "
        "a subjective criterion. Put an unsupported criterion in "
        "`missing_data` and say that it cannot be rated from the supplied "
        "sections."
    )
    data = {"question": question, "sections": safe_sections}
    if agent_context:
        data["specialist_reports"] = agent_context
    payload = json.dumps(data, ensure_ascii=False)
    try:
        return service._llm.complete_json(prompt, payload, FINAL_SCHEMA)
    except AgentError as exc:
        _log.warning("final synthesis degraded: %s", exc)
        return _final_fallback(sections, str(exc))


def _final_fallback(sections: List[dict], reason: str = "") -> dict:
    completed = [item for item in sections if item["status"] == "completed"]
    return {
        "headline": "סיכום חלקי: %d מתוך %d חלקים הושלמו." % (
            len(completed), len(sections)
        ),
        "summary": "\n\n".join(item["summary"] for item in sections),
        "coverage": "; ".join(
            "%s: %s" % (item["name"], item["coverage"])
            for item in sections if item.get("coverage")
        ),
        "key_findings": [fact for item in sections for fact in item["facts"]],
        "risks": [],
        "missing_data": (
            [warning for item in sections for warning in item["warnings"]]
            + (["מודל השפה לא השלים את הסיכום הסופי: " + reason]
               if reason else [])
        ),
        "suggested_questions": [
            question for item in sections
            for question in item["suggested_questions"]
        ],
        "skill_results": [],
        "degraded": True,
    }


def run_skills(service, question, skills, sections, safe_sections) -> List[dict]:
    """Run each selected Skill in its own LLM call.

    One shared call forced every Skill to share a token budget and a single
    generic schema, so a Skill's own instructions competed with the others'
    for attention. A dedicated call puts its full guidance in the system
    prompt against a narrow schema. Skills are independent, so they run
    concurrently; one failing Skill never discards another's result.
    """
    if not skills:
        return []
    source_names = _source_names(sections)
    payload = json.dumps(
        {"question": question, "sections": safe_sections}, ensure_ascii=False
    )
    results = _skill_results(service, skills, payload, source_names)
    # Order follows the user's selection, not thread completion order.
    ordered = [
        results[item["content_key"]] for item in skills
        if item["content_key"] in results
    ]
    for result in ordered:
        result.pop("_raw_sources", None)
    return ordered


def preview_skill(service, name, content, question, sections) -> dict:
    """Run unsaved Skill instructions against sample sections.

    Judging a Skill through a full summary confuses a wording problem with a
    package failure. This isolates the wording question: no package runs and
    nothing is persisted, while the same source validation as production
    applies — so a Skill citing an invented section shows it here.
    """
    skill = {
        "content_key": "skill-preview",
        "name": name or "טיוטת Skill",
        "content": content,
    }
    source_names = {
        value for section in sections
        for value in (section.get("name", ""), section.get("workflow_key", ""))
        if value
    }
    payload = json.dumps(
        {"question": question, "sections": sections}, ensure_ascii=False
    )
    result = run_skill(service, skill, payload, source_names)
    dropped = [
        source for source in result.pop("_raw_sources", [])
        if source not in source_names
    ]
    return {"result": result, "dropped_sources": dropped}


def _source_names(sections: List[dict]) -> set:
    return {
        value for section in sections
        for value in (section["name"], section["workflow_key"])
    }


def _skill_results(service, skills, payload, source_names) -> Dict[str, dict]:
    results = {}
    with ThreadPoolExecutor(max_workers=skill_workers(service, skills)) as pool:
        futures = {
            pool.submit(service._run_skill, skill, payload, source_names): skill
            for skill in skills
        }
        for future in as_completed(futures):
            skill = futures[future]
            results[skill["content_key"]] = _skill_result(
                service, future, skill
            )
    return results


def _skill_result(service, future, skill) -> dict:
    try:
        return future.result()
    except Exception:
        return service._skill_failure(skill)


def skill_workers(service, skills: List[dict]) -> int:
    try:
        limit = service._store.get().max_parallel_workflows
    except AttributeError:
        limit = 1
    return max(1, min(limit, len(skills)))


def run_skill(service, skill, payload, source_names) -> dict:
    system = _skill_prompt(skill["content"])
    try:
        result = service._llm.complete_json(system, payload, SKILL_SCHEMA)
    except AgentError as exc:
        return skill_failure(skill, str(exc))
    return valid_skill_result(result, skill, source_names)


def _skill_prompt(content: str) -> str:
    return (
        content
        + "\n\nUse only facts from the supplied summary sections. Do not add "
        "new information."
        "\nReturn JSON with `summary`, `items`, and `sources`. `sources` may "
        "contain only names of supplied summary sections. If the facts do "
        "not support an answer, say so in `summary` and return an empty "
        "`items`. Write all output text in Hebrew."
    )


def valid_skill_result(result, skill, source_names) -> dict:
    """Enforce the evidence rule: a cited source must be a real section.

    `_raw_sources` records what the model originally cited so `preview_skill`
    can show an FDE which citations were rejected. `run_skills` strips it
    before any result reaches a user.
    """
    result = result if isinstance(result, dict) else {}
    items, sources = result.get("items", []), result.get("sources", [])
    sources = [str(item) for item in sources] if isinstance(sources, list) else []
    return {
        "skill_key": skill["content_key"],
        "name": skill["name"],
        "summary": str(result.get("summary", "")),
        "items": [str(item) for item in items[:8]]
        if isinstance(items, list) else [],
        "sources": [item for item in sources if item in source_names],
        "_raw_sources": sources,
    }


def skill_failure(skill, reason="") -> dict:
    suffix = ": " + reason if reason else "."
    return {
        "skill_key": skill["content_key"],
        "name": skill["name"],
        "summary": "לא ניתן היה להפעיל את ה-Skill" + suffix,
        "items": [],
        "sources": [],
    }
