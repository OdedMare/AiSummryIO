"""Validated published-workflow execution and evidence-backed synthesis."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List

from app.common.errors import AgentError
from app.repository import Repository

_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
    },
    "required": ["summary", "facts", "warnings", "suggested_questions"],
    "additionalProperties": False,
}

_FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {
            "type": "array", "items": {"type": "string"}
        },
    },
    "required": [
        "summary", "key_findings", "risks",
        "missing_data", "suggested_questions",
    ],
    "additionalProperties": False,
}

_WORKFLOW_PLAN_SCHEMA = {
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
                    "summary_prompt": {"type": "string"},
                },
                "required": [
                    "key", "name", "package_version_id", "depends_on",
                    "input_source", "input_field", "summary_prompt",
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


class SummaryService:
    def __init__(self, repository, provider, llm, settings_store):
        self._repository = repository
        self._provider = provider
        self._llm = llm
        self._store = settings_store

    def full_summary(self, run: dict, conversation: dict, progress) -> dict:
        workflows = self._repository.published_workflows(["baseline", "both"])
        return self._execute(
            run, conversation["root_id"], run["question"], workflows, progress
        )

    def follow_up(self, run: dict, conversation: dict, progress) -> dict:
        prior = [
            item for old_run in conversation.get("runs", [])
            if old_run.get("status") in ("completed", "partial")
            for item in self._repository.run_evidence(old_run["id"])
        ]
        details = self._repository.published_workflows(["detail", "both"])
        tools = self._repository.agent_tools()
        selected = self._select_detail(
            run["question"], details, prior, tools=tools
        )
        if selected.get("clarification"):
            return {
                "summary": selected["clarification"],
                "key_findings": [], "risks": [], "missing_data": [],
                "suggested_questions": [
                    workflow["name"] for workflow in details
                ] + [tool["name"] for tool in tools],
                "sections": [], "partial": False, "needs_clarification": True,
            }
        workflows = [
            item for item in details
            if item["workflow_key"] == selected.get("workflow_key")
        ]
        selected_tool = next((
            item for item in tools
            if item["id"] == selected.get("tool_version_id")
        ), None)
        if selected_tool:
            workflows = [self._tool_workflow(selected_tool)]
        if workflows:
            return self._execute(
                run, conversation["root_id"], run["question"], workflows, progress
            )
        return self._synthesize_cached(run["question"], prior)

    def plan_workflow(self, prompt: str) -> dict:
        tools = self._repository.list_packages()
        if not tools:
            return {
                "can_build": False,
                "name": "", "description": "", "role": "detail",
                "rationale": "אין טולים בקטלוג.",
                "system_prompt": "", "steps": [],
                "missing_tools": [{
                    "name": "טול ראשון",
                    "reason": "הקטלוג ריק ולכן אי אפשר להרכיב workflow.",
                    "input_description": "מזהה ראשי כמחרוזת",
                    "output_description": "עובדות מובנות לסיכום",
                }],
            }
        catalog = []
        for tool in tools:
            output_fields = sorted({
                str(field)
                for row in tool.get("example_output", [])
                if isinstance(row, dict)
                for field in row
            })
            catalog.append({
                "tool_version_id": tool["id"],
                "name": tool["name"],
                "description": tool.get("description", ""),
                "agent_instructions": tool.get("agent_instructions", ""),
                "input_mode": tool["input_mode"],
                "input_parameter": tool["input_cube_parameter"],
                "output_fields": output_fields,
            })
        system = self._repository.published_content(
            "workflow-planner",
            "הרכב טיוטת workflow רק מהטולים שסופקו; ציין מה חסר.",
        )
        plan = self._llm.complete_json(
            system,
            json.dumps(
                {"fde_prompt": prompt, "available_tools": catalog},
                ensure_ascii=False,
            ),
            _WORKFLOW_PLAN_SCHEMA,
        )
        return self._validated_plan(plan, tools)

    def dry_run(self, workflow_id: str, root_id: str) -> dict:
        workflow = self._repository.get_workflow(workflow_id)
        fake_run = {"id": "dry-run", "question": "בדיקת FDE"}
        return self._execute_workflow(
            fake_run, root_id, workflow, save_evidence=False
        )

    def _execute(
        self, run, root_id, question, workflows, progress_callback
    ) -> dict:
        if not workflows:
            return self._empty_result("לא פורסמו תהליכי עבודה מתאימים.")
        lock = threading.Lock()
        sections = []
        total = len(workflows)
        progress_callback(0, total, [])
        workers = min(self._store.get().max_parallel_workflows, total)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._execute_workflow, run, root_id, workflow):
                    workflow
                for workflow in workflows
            }
            for future in as_completed(futures):
                workflow = futures[future]
                try:
                    section = future.result()
                except Exception as exc:
                    section = {
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
                with lock:
                    sections.append(section)
                    progress_callback(len(sections), total, list(sections))
        return self._final_summary(root_id, question, sections)

    def _execute_workflow(
        self, run, root_id, workflow, save_evidence=True
    ) -> dict:
        context = {"workflow": {"id": root_id}, "steps": {}}
        warnings, evidence_ids = [], []
        for step in workflow["steps"]:
            package = self._repository.get_package(step["package_version_id"])
            identifiers = self._identifiers(step, context)
            try:
                records = self._run_package(package, identifiers)
            except Exception as exc:
                warnings.append("%s: %s" % (step["name"], exc))
                records = []
            context["steps"][step["key"]] = records
            if save_evidence:
                evidence_ids.append(self._repository.save_evidence(
                    run["id"], workflow["id"], step["key"], records
                ))
        facts = self._chunk_facts(context["steps"])
        prompts = {
            step["key"]: step.get("summary_prompt", "")
            for step in workflow["steps"] if step.get("summary_prompt")
        }
        for fact in facts:
            if fact["step"] in prompts:
                fact["summary_instruction"] = prompts[fact["step"]]
        generated = self._section_summary(workflow, facts, warnings)
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

    def _run_package(self, package: dict, identifiers: List[str]) -> List[dict]:
        if package["input_mode"] == "many":
            return self._provider.run(package, identifiers)
        return [
            record
            for identifier in identifiers
            for record in self._provider.run(package, [identifier])
        ]

    @staticmethod
    def _identifiers(step: dict, context: dict) -> List[str]:
        source = step["input_source"]
        if source == "workflow.id":
            return [str(context["workflow"]["id"])]
        parts = source.split(".")
        if len(parts) < 2 or parts[0] != "steps":
            raise ValueError("מקור קלט לא מוכר: " + source)
        records = context["steps"].get(parts[1])
        if records is None:
            raise ValueError("פלט השלב טרם זמין: " + parts[1])
        field = step.get("input_field") or (parts[-1] if len(parts) > 2 else "")
        if not field:
            raise ValueError("נדרש שדה פלט למיפוי")
        values = []
        for record in records:
            value = record.get(field)
            if isinstance(value, list):
                values.extend(value)
            elif value is not None:
                values.append(value)
        return list(dict.fromkeys(str(value) for value in values))

    @staticmethod
    def _chunk_facts(step_records: Dict[str, List[dict]]) -> List[dict]:
        chunks = []
        for step_key, records in step_records.items():
            for offset in range(0, len(records) or 1, 100):
                rows = records[offset:offset + 100]
                fields = sorted({
                    str(key) for row in rows for key in row.keys()
                })
                samples = {
                    field: list(dict.fromkeys(
                        str(row[field])[:160]
                        for row in rows if row.get(field) is not None
                    ))[:5]
                    for field in fields
                }
                chunks.append({
                    "step": step_key,
                    "chunk": offset // 100 + 1,
                    "row_count": len(rows),
                    "fields": fields,
                    "samples": samples,
                })
        return chunks

    @staticmethod
    def _merge_output_schema(output_schema) -> dict:
        """Extend the section contract with the workflow's own fields.

        The frontend renders summary/facts/warnings/suggested_questions, so an
        FDE schema adds fields rather than replacing them. A malformed schema
        degrades to the shared contract instead of failing the run.
        """
        if not isinstance(output_schema, dict):
            return _SECTION_SCHEMA
        extra = output_schema.get("properties")
        if not isinstance(extra, dict) or not extra:
            return _SECTION_SCHEMA
        properties = dict(_SECTION_SCHEMA["properties"])
        for name, definition in extra.items():
            if name not in properties and isinstance(definition, dict):
                properties[name] = definition
        required = list(_SECTION_SCHEMA["required"])
        for name in output_schema.get("required", []):
            if name in properties and name not in required:
                required.append(name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    def _section_summary(
        self, workflow: dict, facts: List[dict], warnings: List[str]
    ) -> dict:
        system = workflow.get("system_prompt") or (
            "סכם בעברית את עובדות תהליך העבודה. אל תוסיף מידע שלא קיים."
        )
        user = json.dumps(
            {"workflow": workflow["name"], "facts": facts, "warnings": warnings},
            ensure_ascii=False,
        )
        schema = self._merge_output_schema(workflow.get("output_schema"))
        try:
            result = self._llm.complete_json(system, user, schema)
            contract = set(_SECTION_SCHEMA["properties"])
            return {
                "summary": str(result.get("summary", "")),
                "facts": list(result.get("facts", [])),
                "warnings": list(result.get("warnings", [])),
                "suggested_questions": list(
                    result.get("suggested_questions", [])
                ),
                "fields": {
                    key: value
                    for key, value in result.items()
                    if key not in contract
                },
            }
        except AgentError:
            count = sum(item["row_count"] for item in facts)
            return {
                "summary": "נאספו %d רשומות בתהליך %s." % (
                    count, workflow["name"]
                ),
                "facts": [
                    "%s: %d רשומות" % (item["step"], item["row_count"])
                    for item in facts
                ],
                "warnings": [],
                "suggested_questions": [],
                "fields": {},
            }

    def _final_summary(
        self, root_id: str, question: str, sections: List[dict]
    ) -> dict:
        prompt = self._repository.published_content(
            "final-summary",
            "סכם בעברית על סמך העובדות בלבד והחזר JSON.",
        )
        safe_sections = [{
            key: section[key]
            for key in ("name", "status", "summary", "facts", "warnings")
        } for section in sections]
        try:
            final = self._llm.complete_json(
                prompt,
                json.dumps(
                    {"question": question, "sections": safe_sections},
                    ensure_ascii=False,
                ),
                _FINAL_SCHEMA,
            )
        except AgentError:
            final = {
                "summary": "\n\n".join(
                    section["summary"] for section in sections
                ),
                "key_findings": [
                    fact for section in sections for fact in section["facts"]
                ],
                "risks": [],
                "missing_data": [
                    warning
                    for section in sections for warning in section["warnings"]
                ],
                "suggested_questions": [
                    question
                    for section in sections
                    for question in section["suggested_questions"]
                ],
            }
        final["sections"] = sections
        final["partial"] = any(
            section["status"] != "completed" for section in sections
        )
        return final

    def _select_detail(
        self, question: str, workflows: List[dict], evidence: List[dict],
        tools=None,
    ) -> dict:
        tools = tools or []
        if not workflows and not tools:
            if evidence:
                return {"action": "use_cached", "workflow_key": None}
            return {
                "action": "clarify",
                "workflow_key": None,
                "clarification": "אין עדיין תהליך מפורסם שיכול לענות על השאלה.",
            }
        prompt = self._repository.published_content(
            "tool-aware-router",
            "בחר ראיות קיימות, workflow, טול עצמאי או clarification.",
        )
        options = [{
            "workflow_key": item["workflow_key"],
            "name": item["name"],
            "description": item["description"],
        } for item in workflows]
        tool_options = [{
            "tool_version_id": item["id"],
            "name": item["name"],
            "description": item.get("description", ""),
            "agent_instructions": item.get("agent_instructions", ""),
        } for item in tools]
        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["use_cached", "workflow", "tool", "clarify"],
                },
                "workflow_key": {"type": ["string", "null"]},
                "tool_version_id": {"type": ["string", "null"]},
                "clarification": {"type": ["string", "null"]},
            },
            "required": [
                "action", "workflow_key", "tool_version_id", "clarification"
            ],
            "additionalProperties": False,
        }
        evidence_by_step = {}
        for item in evidence:
            evidence_by_step.setdefault(item["step_key"], []).extend(
                item["records"]
            )
        evidence_summary = self._chunk_facts(evidence_by_step)[:20]
        try:
            selected = self._llm.complete_json(
                prompt,
                json.dumps(
                    {
                        "question": question,
                        "available_workflows": options,
                        "available_tools": tool_options,
                        "existing_evidence": evidence_summary,
                    },
                    ensure_ascii=False,
                ),
                schema,
            )
            valid_keys = {item["workflow_key"] for item in workflows}
            valid_tools = {item["id"] for item in tools}
            if (
                selected.get("action") == "workflow"
                and selected.get("workflow_key") not in valid_keys
            ):
                return {
                    "action": "clarify",
                    "workflow_key": None,
                    "clarification": "לאיזה נושא תרצו להעמיק?",
                }
            if (
                selected.get("action") == "tool"
                and selected.get("tool_version_id") not in valid_tools
            ):
                return {
                    "action": "clarify",
                    "workflow_key": None,
                    "tool_version_id": None,
                    "clarification": "לאיזה נושא תרצו להעמיק?",
                }
            if selected.get("action") == "use_cached" and not evidence:
                choices = len(workflows) + len(tools)
                if choices == 1 and workflows:
                    return {
                        "action": "workflow",
                        "workflow_key": workflows[0]["workflow_key"],
                    }
                if choices == 1:
                    return {
                        "action": "tool",
                        "workflow_key": None,
                        "tool_version_id": tools[0]["id"],
                    }
                return {
                    "action": "clarify",
                    "workflow_key": None,
                    "clarification": "לאיזה נושא תרצו להעמיק?",
                }
            return selected
        except AgentError:
            if evidence:
                return {"action": "use_cached", "workflow_key": None}
            if len(workflows) + len(tools) == 1 and workflows:
                return {
                    "action": "workflow",
                    "workflow_key": workflows[0]["workflow_key"],
                }
            if len(workflows) + len(tools) == 1:
                return {
                    "action": "tool",
                    "workflow_key": None,
                    "tool_version_id": tools[0]["id"],
                }
            return {
                "action": "clarify",
                "clarification": "לאיזה נושא תרצו להעמיק?",
                "workflow_key": None,
            }

    @staticmethod
    def _tool_workflow(tool: dict) -> dict:
        instructions = (
            tool.get("agent_instructions")
            or tool.get("description")
            or "סכם בעברית רק את עובדות הטול."
        )
        return {
            "id": "tool:" + tool["id"],
            "workflow_key": "tool:" + tool["package_key"],
            "name": tool["name"],
            "description": tool.get("description", ""),
            "system_prompt": instructions,
            "output_schema": {},
            "steps": [{
                "key": "tool",
                "name": tool["name"],
                "package_version_id": tool["id"],
                "depends_on": [],
                "input_source": "workflow.id",
                "input_field": "",
                "summary_prompt": instructions,
            }],
        }

    @staticmethod
    def _validated_plan(plan: dict, tools: List[dict]) -> dict:
        valid_ids = {tool["id"] for tool in tools}
        missing = list(plan.get("missing_tools", []))
        steps = list(plan.get("steps", []))
        unknown = [
            step for step in steps
            if step.get("package_version_id") not in valid_ids
        ]
        if unknown:
            missing.append({
                "name": "טול שלא קיים בקטלוג",
                "reason": "הצעת המודל כללה מזהה טול שאינו קיים.",
                "input_description": "",
                "output_description": "",
            })
            steps = []
        try:
            Repository._validate_steps(steps)
        except ValueError as exc:
            missing.append({
                "name": "מיפוי שלבים",
                "reason": str(exc),
                "input_description": "פלט משלב מוקדם",
                "output_description": "מזהה קלט לשלב הבא",
            })
            steps = []
        return {
            "can_build": bool(steps),
            "name": str(plan.get("name", "")),
            "description": str(plan.get("description", "")),
            "role": (
                plan.get("role")
                if plan.get("role") in ("baseline", "detail", "both")
                else "detail"
            ),
            "rationale": str(plan.get("rationale", "")),
            "system_prompt": str(plan.get("system_prompt", "")),
            "steps": steps,
            "missing_tools": missing,
        }

    def _synthesize_cached(self, question: str, evidence: List[dict]) -> dict:
        records_by_step = {}
        for item in evidence:
            records_by_step.setdefault(item["step_key"], []).extend(
                item["records"]
            )
        facts = self._chunk_facts(records_by_step)
        generated = self._section_summary(
            {"name": "ראיות קיימות", "system_prompt": ""}, facts, []
        )
        return {
            "summary": generated["summary"],
            "key_findings": generated["facts"],
            "risks": generated["warnings"],
            "missing_data": [],
            "suggested_questions": generated["suggested_questions"],
            "sections": [],
            "partial": False,
        }

    @staticmethod
    def _empty_result(message: str) -> dict:
        return {
            "summary": message, "key_findings": [], "risks": [],
            "missing_data": [], "suggested_questions": [],
            "sections": [], "partial": True,
        }
