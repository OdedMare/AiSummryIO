"""Validated published-workflow execution and evidence-backed synthesis."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List

from app.common.errors import AgentError

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
        selected = self._select_detail(run["question"], details, prior)
        if selected.get("clarification"):
            return {
                "summary": selected["clarification"],
                "key_findings": [], "risks": [], "missing_data": [],
                "suggested_questions": [
                    workflow["name"] for workflow in details
                ],
                "sections": [], "partial": False, "needs_clarification": True,
            }
        workflows = [
            item for item in details
            if item["workflow_key"] == selected.get("workflow_key")
        ]
        if workflows:
            return self._execute(
                run, conversation["root_id"], run["question"], workflows, progress
            )
        return self._synthesize_cached(run["question"], prior)

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
        try:
            result = self._llm.complete_json(system, user, _SECTION_SCHEMA)
            return {
                "summary": str(result.get("summary", "")),
                "facts": list(result.get("facts", [])),
                "warnings": list(result.get("warnings", [])),
                "suggested_questions": list(
                    result.get("suggested_questions", [])
                ),
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
        self, question: str, workflows: List[dict], evidence: List[dict]
    ) -> dict:
        if not workflows:
            if evidence:
                return {"action": "use_cached", "workflow_key": None}
            return {
                "action": "clarify",
                "workflow_key": None,
                "clarification": "אין עדיין תהליך מפורסם שיכול לענות על השאלה.",
            }
        prompt = self._repository.published_content(
            "follow-up-router", "בחר workflow_key מתאים או clarification."
        )
        options = [{
            "workflow_key": item["workflow_key"],
            "name": item["name"],
            "description": item["description"],
        } for item in workflows]
        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["use_cached", "workflow", "clarify"],
                },
                "workflow_key": {"type": ["string", "null"]},
                "clarification": {"type": ["string", "null"]},
            },
            "required": ["action", "workflow_key", "clarification"],
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
                        "existing_evidence": evidence_summary,
                    },
                    ensure_ascii=False,
                ),
                schema,
            )
            valid_keys = {item["workflow_key"] for item in workflows}
            if (
                selected.get("action") == "workflow"
                and selected.get("workflow_key") not in valid_keys
            ):
                return {
                    "action": "clarify",
                    "workflow_key": None,
                    "clarification": "לאיזה נושא תרצו להעמיק?",
                }
            if selected.get("action") == "use_cached" and not evidence:
                if len(workflows) == 1:
                    return {
                        "action": "workflow",
                        "workflow_key": workflows[0]["workflow_key"],
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
            if len(workflows) == 1:
                return {
                    "action": "workflow",
                    "workflow_key": workflows[0]["workflow_key"],
                }
            return {
                "action": "clarify",
                "clarification": "לאיזה נושא תרצו להעמיק?",
                "workflow_key": None,
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


class JobRunner:
    def __init__(self, repository, service, workers=4):
        self._repository = repository
        self._service = service
        worker_count = max(2, workers)
        self._full_pool = ThreadPoolExecutor(max_workers=worker_count - 1)
        self._follow_up_pool = ThreadPoolExecutor(max_workers=1)
        self._submitted = set()
        self._lock = threading.Lock()

    def recover(self) -> None:
        for run in self._repository.queued_runs():
            self.submit(run["id"])

    def submit(self, run_id: str) -> None:
        run = self._repository.get_run(run_id)
        with self._lock:
            if run_id in self._submitted:
                return
            self._submitted.add(run_id)
        pool = (
            self._follow_up_pool
            if run["kind"] == "follow_up"
            else self._full_pool
        )
        pool.submit(self._execute, run_id)

    def _execute(self, run_id: str) -> None:
        try:
            run = self._repository.update_run(run_id, status="running")
            conversation = self._repository.get_conversation(
                run["conversation_id"]
            )

            def progress(completed, total, sections):
                self._repository.update_run(
                    run_id,
                    progress={
                        "completed": completed,
                        "total": total,
                        "sections": sections,
                    },
                )

            if run["kind"] == "full":
                result = self._service.full_summary(
                    run, conversation, progress
                )
            else:
                result = self._service.follow_up(
                    run, conversation, progress
                )
            status = "partial" if result.get("partial") else "completed"
            self._repository.update_run(
                run_id, status=status, result=result,
                finished_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            self._repository.update_run(
                run_id, status="failed", error=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            with self._lock:
                self._submitted.discard(run_id)
