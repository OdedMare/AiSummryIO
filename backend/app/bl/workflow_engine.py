"""Public facade for workflow execution, routing, planning, and synthesis."""

from typing import Dict, List

from app.bl.workflow_engine_pkg import (
    conversational_planning, execution, planning, routing, synthesis,
)
from app.bl.workflow_engine_pkg.schemas import (
    FINAL_SCHEMA, SECTION_SCHEMA, SKILL_SCHEMA, WORKFLOW_PLAN_SCHEMA,
    merge_output_schema,
)

# Kept as aliases because tests and older callers import these contracts.
_SECTION_SCHEMA = SECTION_SCHEMA
_FINAL_SCHEMA = FINAL_SCHEMA
_SKILL_SCHEMA = SKILL_SCHEMA
_WORKFLOW_PLAN_SCHEMA = WORKFLOW_PLAN_SCHEMA


class SummaryService:
    """Stable application-facing API over small behavior modules."""

    def __init__(self, repository, provider, llm, settings_store):
        self._repository = repository
        self._provider = provider
        self._llm = llm
        self._store = settings_store

    def full_summary(self, run: dict, conversation: dict, progress) -> dict:
        workflows = self._repository.published_workflows(["baseline", "both"])
        keys = run.get("skill_keys", [])
        skills = self._repository.published_summary_skills(keys) if keys else []
        return self._execute(
            run, conversation["root_id"], run["question"], workflows, progress,
            skills, conversation.get("boundaries"),
        )

    def follow_up(self, run: dict, conversation: dict, progress) -> dict:
        return routing.follow_up(self, run, conversation, progress)

    def plan_workflow(self, prompt: str) -> dict:
        return planning.plan_workflow(self, prompt)

    def inspect_tool(self, package: dict, root_id: str) -> dict:
        return planning.inspect_tool(self, package, root_id)

    def plan_tool_chat(
        self, messages: List[dict], draft: Dict, inspection: Dict,
        focus_field: str = "",
    ) -> dict:
        return conversational_planning.plan_tool_chat(
            self, messages, draft, inspection, focus_field
        )

    def plan_workflow_chat(
        self, messages: List[dict], draft: Dict, focus_field: str = "",
    ) -> dict:
        return conversational_planning.plan_workflow_chat(
            self, messages, draft, focus_field
        )

    def preview_skill(
        self, name: str, content: str, question: str, sections: List[dict]
    ) -> dict:
        return synthesis.preview_skill(
            self, name, content, question, sections
        )

    def dry_run(self, workflow_id: str, root_id: str) -> dict:
        workflow = self._repository.get_workflow(workflow_id)
        run = {"id": "dry-run", "question": "בדיקת FDE"}
        return self._execute_workflow(run, root_id, workflow, False)

    def _execute(
        self, run, root_id, question, workflows, progress_callback,
        skills=None, boundaries=None,
    ) -> dict:
        return execution.execute(
            self, run, root_id, question, workflows, progress_callback,
            skills, boundaries,
        )

    def _execute_workflow(
        self, run, root_id, workflow, save_evidence=True, boundaries=None
    ) -> dict:
        return execution.execute_workflow(
            self, run, root_id, workflow, save_evidence, boundaries
        )

    def _run_package(
        self, package: dict, identifiers: List[str]
    ) -> List[dict]:
        return execution.run_package(self, package, identifiers)

    @staticmethod
    def _identifiers(step: dict, context: dict) -> List[str]:
        return execution.identifiers(step, context)

    @staticmethod
    def _chunk_facts(step_records: Dict[str, List[dict]]) -> List[dict]:
        return execution.chunk_facts(step_records)

    @staticmethod
    def _merge_output_schema(output_schema) -> dict:
        return merge_output_schema(output_schema)

    def _section_summary(
        self, workflow: dict, facts: List[dict], warnings: List[str]
    ) -> dict:
        return synthesis.section_summary(self, workflow, facts, warnings)

    def _final_summary(
        self, root_id: str, question: str, sections: List[dict], skills=None
    ) -> dict:
        return synthesis.final_summary(
            self, root_id, question, sections, skills
        )

    def _run_skills(
        self, question: str, skills: List[dict], sections: List[dict],
        safe_sections: List[dict],
    ) -> List[dict]:
        return synthesis.run_skills(
            self, question, skills, sections, safe_sections
        )

    def _skill_workers(self, skills: List[dict]) -> int:
        return synthesis.skill_workers(self, skills)

    def _run_skill(self, skill: dict, payload: str, source_names) -> dict:
        return synthesis.run_skill(self, skill, payload, source_names)

    @staticmethod
    def _valid_skill_result(result, skill: dict, source_names) -> dict:
        return synthesis.valid_skill_result(result, skill, source_names)

    @staticmethod
    def _skill_failure(skill: dict, reason: str = "") -> dict:
        return synthesis.skill_failure(skill, reason)

    def _select_detail(
        self, question: str, workflows: List[dict], evidence: List[dict],
        tools=None, turns=None,
    ) -> dict:
        return routing.select_detail(
            self, question, workflows, evidence, tools, turns
        )

    @staticmethod
    def _tool_workflow(tool: dict) -> dict:
        return routing.tool_workflow(tool)

    @staticmethod
    def _validated_plan(plan: dict, tools: List[dict]) -> dict:
        return planning.validated_plan(plan, tools)

    @staticmethod
    def _infer_output_schema(records: List[dict]) -> dict:
        return planning.infer_output_schema(records)

    @staticmethod
    def _json_type(value) -> str:
        return planning.json_type(value)

    def _synthesize_cached(
        self, question: str, evidence: List[dict], skills=None
    ) -> dict:
        return routing.synthesize_cached(self, question, evidence, skills)

    @staticmethod
    def _empty_result(message: str) -> dict:
        return execution.empty_result(message)
