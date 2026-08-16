"""Skills and prompts, plus unsaved-Skill preview."""

from fastapi import APIRouter, Depends

from app.api.models import AgentContentCreate, PlanChatCreate, SkillPreview


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/agent-content", tags=["agent-content"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def agent_content():
        return context.repository.list_agent_content()

    @router.post("")
    def create_agent_content(payload: AgentContentCreate):
        return context.repository.create_agent_content(payload.model_dump())

    @router.put("/{content_id}")
    def update_agent_content(content_id: str, payload: AgentContentCreate):
        return context.repository.update_agent_content(
            content_id, payload.model_dump()
        )

    @router.post("/preview-skill")
    def preview_skill(payload: SkillPreview):
        return context.service.preview_skill(
            payload.name,
            payload.content,
            payload.question,
            [section.model_dump() for section in payload.sections],
        )

    @router.post("/plan-skill-chat")
    def plan_skill_chat(payload: PlanChatCreate):
        return context.service.plan_skill_chat(
            [item.model_dump() for item in payload.messages], payload.draft,
            payload.focus_field,
        )

    @router.post("/plan-specialist-chat")
    def plan_specialist_chat(payload: PlanChatCreate):
        return context.service.plan_specialist_chat(
            [item.model_dump() for item in payload.messages], payload.draft,
            payload.focus_field,
        )

    @router.delete("/{content_id}")
    def delete_agent_content(content_id: str):
        return context.repository.delete_agent_content(content_id)

    return router
