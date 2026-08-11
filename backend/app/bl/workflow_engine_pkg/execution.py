"""Workflow and package execution."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List

from app.common.geometry import multipolygon_to_wkt
from app.common.logging_setup import trace
from app.dal.repository.validation import step_levels

_log = trace("execution")

# Routing and specialist follow-ups use a bounded digest. Section synthesis
# uses the same size as a batch and analyzes every batch before reducing them.
_SUMMARY_ROW_LIMIT = 100


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
    """Narrow the agent-enabled workflows to those the request can satisfy."""
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
            "אין תהליך עבודה פעיל שמקבל אזור על המפה."
            if boundaries and not root_id
            else "אין תהליכי עבודה פעילים מתאימים."
        )
    sections = _execute_all(
        service, run, root_id, workflows, progress_callback, boundaries
    )
    return service._final_summary(root_id, question, sections, skills or [])


def execute_sections(
    service, run, root_id, workflows, progress_callback, boundaries=None
) -> List[dict]:
    """Execute selected workflows without consuming them in final synthesis."""
    workflows = select_workflows(workflows, root_id, boundaries)
    if not workflows:
        progress_callback(0, 0, [])
        return []
    return _execute_all(
        service, run, root_id, workflows, progress_callback, boundaries
    )


def _execute_all(
    service, run, root_id, workflows, progress_callback, boundaries
) -> List[dict]:
    total = len(workflows)
    progress_callback(0, total, [])
    workers = min(service._store.get().max_parallel_workflows, total)
    _log.info(
        "executing %d workflow(s) on %d worker(s): %s", total, workers,
        ", ".join(item["workflow_key"] for item in workflows),
    )
    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = _workflow_futures(
            pool, service, run, root_id, workflows, boundaries
        )
        sections = _collect_sections(futures, total, progress_callback)
    _log.info(
        "all %d workflow(s) finished in %.2fs", total, time.time() - started,
    )
    return sections


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
        section = future.result()
        _log.info(
            "workflow OK  %s status=%s facts=%d warnings=%d",
            workflow["workflow_key"], section.get("status"),
            len(section.get("facts", [])), len(section.get("warnings", [])),
        )
        return section
    except Exception as exc:
        _log.exception(
            "workflow FAILED %s %s: %s",
            workflow["workflow_key"], type(exc).__name__, exc,
        )
        return _failed_section(workflow, exc)


def _failed_section(workflow: dict, exc: Exception) -> dict:
    return {
        "workflow_id": workflow["id"],
        "workflow_key": workflow["workflow_key"],
        "name": workflow["name"],
        "status": "failed",
        "summary": "תהליך העבודה נכשל.",
        "coverage": "לא נאספו נתונים",
        "facts": [],
        "patterns": [],
        "outliers": [],
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
    facts = fact_chunks(context["steps"], context["summary_fields"])
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
    levels = step_levels(workflow["steps"])
    _log.info(
        "workflow %s: %d step(s) in %d level(s) -> %s",
        workflow["workflow_key"], len(workflow["steps"]), len(levels),
        " then ".join(
            "[" + ", ".join(step["key"] for step in level) + "]"
            for level in levels
        ),
    )
    for index, level in enumerate(levels):
        _log.info(
            "workflow %s: level %d/%d starting (%d step(s) concurrently)",
            workflow["workflow_key"], index + 1, len(levels), len(level),
        )
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
    key = step["key"]
    started = time.time()
    _log.info(
        "step START %s (package_version=%s source=%s field=%s)",
        key, step["package_version_id"], step.get("input_source"),
        step.get("input_field") or "-",
    )
    package = service._repository.get_package(step["package_version_id"])
    fields = _summary_fields(package)
    try:
        resolved = service._identifiers(step, context)
        _log.info(
            "step %s resolved %d identifier(s) for package %s",
            key, len(resolved), package.get("package_key"),
        )
        _log.debug("step %s identifiers=%s", key, _preview(resolved))
        records = service._run_package(package, resolved)
        _log.info(
            "step OK    %s rows=%d in %.2fs",
            key, len(records), time.time() - started,
        )
    except Exception as exc:
        # A step failure is a warning, not an abort — but it must be visible,
        # or a section quietly returns empty with the cause only in the UI.
        _log.warning(
            "step FAIL  %s after %.2fs %s: %s",
            key, time.time() - started, type(exc).__name__, exc,
        )
        _log.debug("step %s traceback", key, exc_info=True)
        warnings.append("%s: %s" % (step["name"], exc))
        records = []
    return records, warnings, fields


def _preview(values: List[str], limit: int = 5) -> str:
    """A bounded sample of identifiers — never the whole list, which can be
    thousands of rows fanned out from a previous step."""
    shown = [str(value)[:60] for value in values[:limit]]
    extra = len(values) - len(shown)
    return ", ".join(shown) + (" (+%d more)" % extra if extra > 0 else "")


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
        "coverage": generated.get("coverage", ""),
        "facts": generated["facts"],
        "patterns": generated.get("patterns", []),
        "outliers": generated.get("outliers", []),
        "warnings": warnings + generated["warnings"],
        "suggested_questions": generated["suggested_questions"],
        "fields": generated.get("fields", {}),
        # True when the section came from `_section_fallback` — the model did
        # not answer and these are counts, not a summary.
        "degraded": generated.get("degraded", False),
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


def identifiers(step: dict, context: dict) -> List[str]:
    source = step["input_source"]
    if source == "workflow.id":
        return _root_identifiers(context)
    if source == "workflow.boundaries":
        return _boundary_identifiers(context)
    if source == "workflow.value":
        return [str(step["input_value"])]
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
    return list(dict.fromkeys(
        _identifier_value(value) for value in _values(records, field)
    ))


def _identifier_value(value) -> str:
    """Keep mapped geometry values as one FLAPI-ready identifier."""
    if isinstance(value, dict) and value.get("type") == "MultiPolygon":
        return multipolygon_to_wkt(value)
    return str(value)


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
    """Build one bounded evidence digest per step.

    This function used to create one item per 100 rows and then send every item
    in a single LLM request. A 6,000-row result therefore still put all 6,000
    rows in the prompt. The digest keeps exact whole-dataset statistics and a
    representative row sample, so prompt size is bounded without pretending
    the sample is the full coverage.
    """
    field_policies = field_policies or {}
    return [
        _fact_chunk(
            step_key, records, field_policies.get(step_key)
        )
        for step_key, records in step_records.items()
    ]


def fact_chunks(
    step_records: Dict[str, List[dict]], field_policies=None
) -> List[dict]:
    """Split every summary-eligible row into bounded, lossless batches."""
    field_policies = field_policies or {}
    result = []
    for step_key, records in step_records.items():
        allowed_fields = field_policies.get(step_key)
        available = {str(key) for row in records for key in row}
        fields = sorted(
            available if allowed_fields is None
            else available.intersection(allowed_fields)
        )
        batches = [
            records[index:index + _SUMMARY_ROW_LIMIT]
            for index in range(0, len(records), _SUMMARY_ROW_LIMIT)
        ] or [[]]
        stats = _stats(records, fields)
        samples = _samples(records, fields)
        for index, batch in enumerate(batches):
            result.append({
                "step": step_key,
                "chunk": index + 1,
                "chunk_count": len(batches),
                "row_count": len(records),
                "chunk_row_count": len(batch),
                "fields": fields,
                "rows": _rows(batch, fields),
                # Global arithmetic is needed once by the reducer, not in
                # every map call over this step's disjoint row batches.
                **({"stats": stats, "samples": samples} if index == 0 else {}),
                "complete_rows": True,
            })
    return result


def _fact_chunk(
    step_key: str, records: List[dict], allowed_fields=None
) -> dict:
    available = {str(key) for row in records for key in row}
    fields = sorted(
        available if allowed_fields is None
        else available.intersection(allowed_fields)
    )
    rows = _representative_rows(records, _SUMMARY_ROW_LIMIT)
    return {
        "step": step_key,
        "chunk": 1,
        "row_count": len(records),
        "sampled_row_count": len(rows),
        "fields": fields,
        # Whole representative rows, so the model can still see which values
        # co-occur without receiving the entire DataFrame.
        "rows": _rows(rows, fields),
        # Arithmetic is computed over all records, never over the bounded
        # sample. This is what makes counts and coverage exact.
        "stats": _stats(records, fields),
        "samples": _samples(records, fields),
    }


def _representative_rows(rows: List[dict], limit: int) -> List[dict]:
    """Evenly sample the full result, including its first and last rows."""
    if len(rows) <= limit:
        return rows
    return [
        rows[index * (len(rows) - 1) // (limit - 1)]
        for index in range(limit)
    ]


def _rows(rows: List[dict], fields: List[str]) -> List[dict]:
    return [
        {
            field: str(row[field])[:160]
            for field in fields if row.get(field) is not None
        }
        for row in rows
    ]


def _samples(rows: List[dict], fields: List[str]) -> dict:
    """Distinct values per field.

    Kept beside `rows` because it stays the quickest way to see a field's
    vocabulary, and an FDE prompt may already refer to it.
    """
    return {
        field: list(dict.fromkeys(
            str(row[field])[:160]
            for row in rows if row.get(field) is not None
        ))[:5]
        for field in fields
    }


def _stats(rows: List[dict], fields: List[str]) -> dict:
    return {
        field: _field_stats(rows, field)
        for field in fields
    }


def _field_stats(rows: List[dict], field: str) -> dict:
    values = [row[field] for row in rows if row.get(field) is not None]
    stats = {"present": len(values), "missing": len(rows) - len(values)}
    texts = [str(value) for value in values]
    distinct = dict.fromkeys(texts)
    stats["distinct"] = len(distinct)
    # A low-cardinality field is categorical: the split is the finding. A
    # high-cardinality one is an identifier or free text, where counting every
    # value would bloat the payload and tell the model nothing.
    if 0 < len(distinct) <= 15:
        counts = {}
        for text in texts:
            counts[text[:160]] = counts.get(text[:160], 0) + 1
        stats["counts"] = dict(sorted(
            counts.items(), key=lambda pair: (-pair[1], pair[0])
        ))
    numbers = _numbers(values)
    if numbers and len(numbers) == len(values):
        stats["min"] = min(numbers)
        stats["max"] = max(numbers)
        stats["mean"] = round(sum(numbers) / len(numbers), 4)
    return stats


def _numbers(values: List) -> List[float]:
    numbers = []
    for value in values:
        if isinstance(value, bool):
            return []
        if isinstance(value, (int, float)):
            numbers.append(float(value))
    return numbers


def empty_result(message: str) -> dict:
    return {
        "headline": message, "summary": message, "coverage": "לא נאספו נתונים",
        "key_findings": [], "risks": [],
        "missing_data": [], "suggested_questions": [],
        "skill_results": [], "sections": [], "partial": True,
    }
