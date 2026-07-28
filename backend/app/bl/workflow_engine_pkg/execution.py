"""Workflow and package execution."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List

from app.common.geometry import multipolygon_to_wkt
from app.dal.repository.validation import step_levels


def geo_capable(workflow: dict) -> bool:
    """True when any step reads the drawn area.

    A geo-only request has no identifier, so a workflow whose every step wants
    ``workflow.id`` could only produce warnings. Selecting on this keeps such
    a run to the workflows that can genuinely answer it.
    """
    return any(
        step.get("input_source") == "workflow.boundaries"
        for step in workflow.get("steps", [])
    )


def select_workflows(workflows: List[dict], root_id, boundaries) -> List[dict]:
    """Narrow the published workflows to those the request can satisfy."""
    if root_id:
        return workflows
    if not boundaries:
        return workflows
    return [item for item in workflows if geo_capable(item)]


def execute(
    service, run, root_id, question, workflows, progress_callback,
    skills=None, boundaries=None,
) -> dict:
    workflows = select_workflows(workflows, root_id, boundaries)
    if not workflows:
        return empty_result(
            "לא פורסם תהליך עבודה שמקבל אזור על המפה."
            if boundaries and not root_id
            else "לא פורסמו תהליכי עבודה מתאימים."
        )
    sections = _execute_all(
        service, run, root_id, workflows, progress_callback, boundaries
    )
    return service._final_summary(root_id, question, sections, skills or [])


def _execute_all(
    service, run, root_id, workflows, progress_callback, boundaries
) -> List[dict]:
    total = len(workflows)
    progress_callback(0, total, [])
    workers = min(service._store.get().max_parallel_workflows, total)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = _workflow_futures(
            pool, service, run, root_id, workflows, boundaries
        )
        return _collect_sections(futures, total, progress_callback)


def _workflow_futures(
    pool, service, run, root_id, workflows, boundaries
) -> dict:
    return {
        pool.submit(
            service._execute_workflow, run, root_id, workflow, True, boundaries
        ): workflow
        for workflow in workflows
    }


def _collect_sections(futures, total: int, progress_callback) -> List[dict]:
    lock = threading.Lock()
    sections = []
    for future in as_completed(futures):
        section = _future_section(future, futures[future])
        with lock:
            sections.append(section)
            progress_callback(len(sections), total, list(sections))
    return sections


def _future_section(future, workflow: dict) -> dict:
    try:
        return future.result()
    except Exception as exc:
        return _failed_section(workflow, exc)


def _failed_section(workflow: dict, exc: Exception) -> dict:
    return {
        "workflow_id": workflow["id"],
        "workflow_key": workflow["workflow_key"],
        "name": workflow["name"],
        "status": "failed",
        "summary": "תהליך העבודה נכשל.",
        "facts": [],
        "warnings": [str(exc)],
        "suggested_questions": [],
        "evidence_ids": [],
    }


def execute_workflow(
    service, run, root_id, workflow, save_evidence=True, boundaries=None
) -> dict:
    context = {
        "workflow": {"id": root_id, "boundaries": boundaries},
        "steps": {}, "summary_fields": {},
    }
    warnings, evidence_ids = _run_steps(
        service, run, workflow, context, save_evidence
    )
    facts = chunk_facts(context["steps"], context["summary_fields"])
    _add_summary_instructions(facts, workflow["steps"])
    generated = service._section_summary(workflow, facts, warnings)
    return _section(workflow, generated, warnings, evidence_ids)


def _run_steps(service, run, workflow, context, save_evidence):
    """Run the workflow's steps, level by level.

    Steps that do not depend on one another are independent package calls, so
    each level runs concurrently. A level completes before the next starts,
    which is what lets a dependent step read its source from
    ``context["steps"]`` without any further coordination.
    """
    warnings, evidence_ids = [], []
    for level in step_levels(workflow["steps"]):
        _run_level(
            service, run, workflow, context, save_evidence, level,
            warnings, evidence_ids,
        )
    return warnings, evidence_ids


def _run_level(
    service, run, workflow, context, save_evidence, level,
    warnings, evidence_ids,
) -> None:
    outcomes = _level_outcomes(service, context, level)
    # Applied in the level's declared order so evidence and warnings stay
    # stable regardless of which package finished first.
    for step in level:
        records, step_warnings, fields = outcomes[step["key"]]
        warnings.extend(step_warnings)
        context["steps"][step["key"]] = records
        context["summary_fields"][step["key"]] = fields
        _save_evidence(service, run, workflow, step, records, evidence_ids,
                       save_evidence)


def _level_outcomes(service, context, level) -> Dict[str, tuple]:
    """Map each step to records, warnings, and its summary-field policy."""
    if len(level) == 1:
        step = level[0]
        return {step["key"]: _step_outcome(service, step, context)}
    workers = min(service._store.get().max_parallel_workflows, len(level))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_step_outcome, service, step, context): step["key"]
            for step in level
        }
        return {
            futures[future]: future.result()
            for future in as_completed(futures)
        }


def _step_outcome(service, step, context) -> tuple:
    """Run one step, keeping its warnings local so threads never share a list."""
    warnings = []
    package = service._repository.get_package(step["package_version_id"])
    fields = _summary_fields(package)
    try:
        records = service._run_package(
            package, service._identifiers(step, context)
        )
    except Exception as exc:
        warnings.append("%s: %s" % (step["name"], exc))
        records = []
    return records, warnings, fields


def _summary_fields(package):
    schema = package.get("output_schema", {})
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if not any(
        isinstance(definition, dict)
        and isinstance(definition.get("x-summary"), bool)
        for definition in properties.values()
    ):
        return None
    return [
        str(field) for field, definition in properties.items()
        if not isinstance(definition, dict)
        or definition.get("x-summary", True)
    ]


def _save_evidence(
    service, run, workflow, step, records, evidence_ids, enabled
) -> None:
    if not enabled:
        return
    evidence_ids.append(service._repository.save_evidence(
        run["id"], workflow["id"], step["key"], records
    ))


def _add_summary_instructions(facts: List[dict], steps: List[dict]) -> None:
    prompts = {
        step["key"]: step.get("summary_prompt", "")
        for step in steps if step.get("summary_prompt")
    }
    for fact in facts:
        if fact["step"] in prompts:
            fact["summary_instruction"] = prompts[fact["step"]]


def _section(workflow, generated, warnings, evidence_ids) -> dict:
    return {
        "workflow_id": workflow["id"],
        "workflow_key": workflow["workflow_key"],
        "name": workflow["name"],
        "status": "partial" if warnings else "completed",
        "summary": generated["summary"],
        "facts": generated["facts"],
        "warnings": warnings + generated["warnings"],
        "suggested_questions": generated["suggested_questions"],
        "fields": generated.get("fields", {}),
        "evidence_ids": evidence_ids,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def run_package(service, package: dict, identifiers: List[str]) -> List[dict]:
    if package["input_mode"] == "many":
        return service._provider.run(package, identifiers)
    return [
        record
        for identifier in identifiers
        for record in service._provider.run(package, [identifier])
    ]


def source_kind(source: str) -> str:
    """The kind of value an ``input_source`` produces.

    ``steps.<key>`` reads a field out of an earlier package's rows, which is
    an identifier by construction — the drawn area only ever enters a run
    through ``workflow.boundaries``.
    """
    return "geometry" if source == "workflow.boundaries" else "id"


def input_kind_mismatch(package: dict, step: dict) -> str:
    """A Hebrew warning when a step feeds a tool a shape it does not accept.

    Deliberately a warning rather than a hard failure: ``input_kind`` was
    added after tools were already in the catalog, so a wrong declaration on
    an existing tool must not take down a workflow that has been running.
    The step still executes and FLAPI remains the authority on the value.
    """
    declared = package.get("input_kind") or "both"
    if declared == "both":
        return ""
    actual = source_kind(step.get("input_source", "workflow.id"))
    if declared == actual:
        return ""
    if declared == "id":
        return "הכלי מוגדר לקבל מזהה בלבד, והשלב מזין אזור מהמפה"
    return "הכלי מוגדר לקבל אזור מהמפה בלבד, והשלב מזין מזהה"


def identifiers(step: dict, context: dict) -> List[str]:
    source = step["input_source"]
    if source == "workflow.id":
        return _root_identifiers(context)
    if source == "workflow.boundaries":
        return _boundary_identifiers(context)
    return _step_identifiers(step, context, source)


def _root_identifiers(context: dict) -> List[str]:
    """The conversation's root identifier.

    A request may now be scoped by a drawn area alone, so this can be absent.
    Raising here is what turns such a step into a visible warning on its
    section instead of silently sending the string "None" to FLAPI.
    """
    root_id = context["workflow"].get("id")
    if root_id is None or str(root_id).strip() == "":
        raise ValueError("לשלב זה נדרש מזהה, והבקשה כוללת אזור בלבד")
    return [str(root_id)]


def _boundary_identifiers(context: dict) -> List[str]:
    wkt = multipolygon_to_wkt(context["workflow"].get("boundaries"))
    if not wkt:
        raise ValueError("לא נבחר אזור על המפה")
    return [wkt]


def _step_identifiers(step: dict, context: dict, source: str) -> List[str]:
    step_key = _source_step(source)
    records = context["steps"].get(step_key)
    if records is None:
        raise ValueError("פלט השלב טרם זמין: " + step_key)
    field = step.get("input_field") or _source_field(source)
    if not field:
        raise ValueError("נדרש שדה פלט למיפוי")
    return list(dict.fromkeys(str(value) for value in _values(records, field)))


def _source_step(source: str) -> str:
    parts = source.split(".")
    if len(parts) < 2 or parts[0] != "steps":
        raise ValueError("מקור קלט לא מוכר: " + source)
    return parts[1]


def _source_field(source: str) -> str:
    parts = source.split(".")
    return parts[-1] if len(parts) > 2 else ""


def _values(records: List[dict], field: str):
    for record in records:
        value = record.get(field)
        if isinstance(value, list):
            yield from value
        elif value is not None:
            yield value


def chunk_facts(
    step_records: Dict[str, List[dict]], field_policies=None
) -> List[dict]:
    field_policies = field_policies or {}
    return [
        _fact_chunk(
            step_key, records, offset, field_policies.get(step_key)
        )
        for step_key, records in step_records.items()
        for offset in range(0, len(records) or 1, 100)
    ]


def _fact_chunk(
    step_key: str, records: List[dict], offset: int, allowed_fields=None
) -> dict:
    rows = records[offset:offset + 100]
    available = {str(key) for row in rows for key in row}
    fields = sorted(
        available if allowed_fields is None
        else available.intersection(allowed_fields)
    )
    return {
        "step": step_key,
        "chunk": offset // 100 + 1,
        "row_count": len(rows),
        "fields": fields,
        "samples": _samples(rows, fields),
    }


def _samples(rows: List[dict], fields: List[str]) -> dict:
    return {
        field: list(dict.fromkeys(
            str(row[field])[:160]
            for row in rows if row.get(field) is not None
        ))[:5]
        for field in fields
    }


def empty_result(message: str) -> dict:
    return {
        "summary": message, "key_findings": [], "risks": [],
        "missing_data": [], "suggested_questions": [],
        "skill_results": [], "sections": [], "partial": True,
    }
