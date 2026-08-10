"""LLM-backed section, final-summary, and Skill synthesis."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from app.common.errors import AgentError
from app.bl.workflow_engine_pkg.schemas import (
    FINAL_SCHEMA, SECTION_SCHEMA, SKILL_SCHEMA, merge_output_schema,
)


# How to read the payload `chunk_facts` produces. Appended to the workflow's
# own prompt rather than replacing it: an FDE writes domain instructions, and
# these describe the data's shape, which is the same for every workflow.
_TABULAR_GUIDANCE = """
מבנה הנתונים: כל פריט ב-facts הוא מקטע של עד 100 שורות, ובו `row_count`,
`rows` (השורות עצמן), ו-`stats` לכל שדה. `stats` מחושב בקוד על כל שורות
המקטע: `present`/`missing`, `distinct`, `counts` (שכיחות, לשדות עם עד 15
ערכים), ו-`min`/`max`/`mean` לשדות מספריים.

כללי קריאה:
1. פתח בהיקף — כמה שורות ובאילו שלבים. `coverage` יכיל זאת במפורש.
2. העדף התפלגות על דוגמה. "263 מתוך 412 פתוחים" הוא ממצא; שורה בודדת אינה.
3. השתמש במספרים מ-`stats` כפי שהם. אל תספור בעצמך ואל תחשב אחוז ללא מכנה.
4. `missing` גבוה בשדה הוא ממצא על כיסוי — ציין אותו.
5. חריגים חשובים מהטיפוסי: תאריך עתידי, סגירה לפני פתיחה, כפילות, ערך קיצוני.

חלוקת הפלט:
- `facts` — ממצאים קונקרטיים על שורות או ישויות.
- `patterns` — התפלגויות, טווחי זמן וריכוזים.
- `outliers` — רשומות חריגות בלבד. ריק אם אין.
- `coverage` — כמה נאסף ומה נכלל, במשפט אחד.

אסור: למנות שורות אחת-אחת; להציג שם שדה כממצא; לקבוע ספירה שאינה ב-`stats`;
להסיק סיבתיות; להתייחס ל-`row_count` כמספר ישויות ייחודיות.
"""


def section_summary(service, workflow, facts, warnings) -> dict:
    system = (workflow.get("system_prompt") or (
        "סכם בעברית את עובדות תהליך העבודה. אל תוסיף מידע שלא קיים."
    )) + _TABULAR_GUIDANCE
    user = json.dumps(
        {"workflow": workflow["name"], "facts": facts, "warnings": warnings},
        ensure_ascii=False,
    )
    schema = merge_output_schema(workflow.get("output_schema"))
    try:
        return _section_result(service._llm.complete_json(system, user, schema))
    except AgentError:
        return _section_fallback(workflow, facts)


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


def _section_fallback(workflow: dict, facts: List[dict]) -> dict:
    """Stated coverage, and `degraded` so the caller can say the model failed.

    Without the flag a reader cannot tell a thin section from a fallback, and
    reads "no information" where the truth is "the model did not answer".
    """
    count = sum(item["row_count"] for item in facts)
    return {
        "summary": "נאספו %d רשומות בתהליך %s." % (count, workflow["name"]),
        "coverage": "%d רשומות ב-%d שלבים" % (count, len(facts)),
        "facts": ["%s: %d רשומות" % (item["step"], item["row_count"])
                  for item in facts],
        "patterns": [],
        "outliers": [],
        "warnings": ["הסיכום הופק ללא מודל השפה; מוצגות ספירות בלבד."],
        "suggested_questions": [],
        "fields": {},
        "degraded": True,
    }


def final_summary(service, root_id, question, sections, skills=None) -> dict:
    skills = skills or []
    safe_sections = [_safe_section(section) for section in sections]
    final = _shared_summary(service, question, sections, safe_sections)
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


def _shared_summary(service, question, sections, safe_sections) -> dict:
    prompt = service._repository.enabled_content(
        "final-summary", "סכם בעברית על סמך העובדות בלבד והחזר JSON."
    )
    prompt += (
        "\nהחזר skill_results כמערך ריק. כל Skill מופעל בקריאה נפרדת."
        "\n`headline` הוא משפט אחד שעונה על השאלה — מי שקורא רק אותו קיבל"
        " את התשובה. אל תפתח בתיאור התהליך או במה שחופש."
        "\n`coverage` מסכם במשפט אחד על כמה נתונים הסיכום נשען, על סמך"
        " שדות ה-coverage של החלקים. אל תרמוז לכיסוי מלא כשחלק נכשל."
        "\n`key_findings` מדורג לפי השפעה על החלטה, לא לפי סדר החלקים."
        " מזג ממצאים חופפים; אל תחזור על ממצא."
        "\nהשתמש ב-patterns וב-outliers של החלקים: התפלגות רחבה שייכת"
        " ל-key_findings רק אם היא משנה מסקנה, וחריג שייך ל-risks."
    )
    payload = json.dumps(
        {"question": question, "sections": safe_sections}, ensure_ascii=False
    )
    try:
        return service._llm.complete_json(prompt, payload, FINAL_SCHEMA)
    except AgentError:
        return _final_fallback(sections)


def _final_fallback(sections: List[dict]) -> dict:
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
        "missing_data": [
            warning for item in sections for warning in item["warnings"]
        ],
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
        + "\n\nהשתמש רק בעובדות שבחלקי הסיכום שסופקו. אל תוסיף מידע חדש."
        "\nהחזר JSON עם summary, items ו-sources. sources יכיל רק שמות"
        " של חלקי סיכום שסופקו. אם אין בסיס בעובדות, אמור זאת ב-summary"
        " והחזר items ריק."
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
