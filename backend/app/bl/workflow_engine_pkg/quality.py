"""Deterministic quality gate and run telemetry.

This runs after synthesis and before the result is persisted.  It deliberately
does not call the model: the gate must still work when the model is unavailable.
"""

from typing import List


def finalize(service, run: dict, result: dict, elapsed_seconds: float) -> dict:
    enriched = dict(result)
    evidence = _evidence(service, run)
    trace = enriched.get("agent_trace") or {}
    sections = enriched.get("sections") or []
    enriched["quality"] = assess(enriched)
    enriched["telemetry"] = {
        "model": _model(service),
        "prompt_revision": _prompt_revision(service),
        "duration_ms": max(0, int(elapsed_seconds * 1000)),
        "tool_calls": len(evidence),
        "evidence_rows": sum(len(item.get("records") or []) for item in evidence),
        "workflow_count": len({
            item.get("workflow_id") for item in sections
            if item.get("workflow_id")
        }),
        "specialist_count": len(trace.get("specialists") or []),
        "rounds_used": int(trace.get("rounds_used") or 0),
        "degraded": bool(enriched.get("degraded")),
        # The current OpenAI-compatible client returns parsed JSON only.  Do
        # not report made-up token or cost numbers until it exposes usage.
        "token_usage_available": False,
    }
    return enriched


def assess(result: dict) -> dict:
    sections = result.get("sections") or []
    claims = result.get("claims") or []
    missing = result.get("missing_data") or []
    reasons: List[str] = []

    completed = sum(item.get("status") == "completed" for item in sections)
    section_ratio = completed / len(sections) if sections else 0.0
    factual = [item for item in claims if item.get("text")]
    cited = sum(bool(item.get("citation_ids")) for item in factual)
    citation_ratio = cited / len(factual) if factual else (1.0 if not sections else 0.0)

    score = 0.55 * section_ratio + 0.45 * citation_ratio
    if result.get("degraded"):
        score -= 0.20
        reasons.append("מודל הסיכום עבר למסלול גיבוי")
    if result.get("partial"):
        score -= 0.10
        reasons.append("לפחות מקור אחד הושלם חלקית")
    if missing:
        score -= min(0.20, 0.04 * len(missing))
        reasons.append("התשובה מציינת פערי מידע")
    if factual and cited < len(factual):
        reasons.append("לא לכל הטענות העובדתיות צורפה ראיה")
    if not sections:
        reasons.append("לא הופעל Workflow מבוסס נתונים")

    score = round(max(0.0, min(1.0, score)), 2)
    level = "high" if score >= 0.8 else "medium" if score >= 0.5 else "low"
    return {
        "score": score,
        "level": level,
        "section_coverage": round(section_ratio, 2),
        "citation_coverage": round(citation_ratio, 2),
        "passed": score >= 0.5 and not result.get("degraded", False),
        "reasons": reasons,
    }


def _evidence(service, run: dict) -> List[dict]:
    reader = getattr(service._repository, "run_evidence", None)
    if not reader or not run.get("id"):
        return []
    try:
        return list(reader(run["id"]))
    except Exception:
        return []


def _model(service) -> str:
    try:
        return str(service._store.get().llm_model)
    except AttributeError:
        return ""


def _prompt_revision(service) -> str:
    reader = getattr(service._repository, "prompt_revision", None)
    if not reader:
        return ""
    try:
        return str(reader())
    except Exception:
        return ""
