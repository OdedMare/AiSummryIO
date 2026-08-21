"""Skills and prompts, plus unsaved-Skill preview."""

from fastapi import APIRouter, Depends

from app.api.models import AgentContentCreate, PlanChatCreate, SkillPreview


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/agent-content", tags=["agent-content"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def agent_content(
        project_id: str, session_id: str = Depends(context.user_session)
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.list_agent_content(project_id)

    @router.post("")
    def create_agent_content(
        payload: AgentContentCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.create_agent_content(
            payload.model_dump(), project_id
        )

    @router.put("/{content_id}")
    def update_agent_content(
        content_id: str, payload: AgentContentCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.update_agent_content(
            content_id, payload.model_dump(), project_id
        )

    @router.post("/preview-skill")
    def preview_skill(
        payload: SkillPreview, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.preview_skill(
            payload.name,
            payload.content,
            payload.question,
            [section.model_dump() for section in payload.sections],
        )

    @router.post("/plan-skill-chat")
    def plan_skill_chat(
        payload: PlanChatCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.plan_skill_chat(
            [item.model_dump() for item in payload.messages], payload.draft,
            payload.focus_field, project_id,
        )

    @router.post("/plan-specialist-chat")
    def plan_specialist_chat(
        payload: PlanChatCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.plan_specialist_chat(
            [item.model_dump() for item in payload.messages], payload.draft,
            payload.focus_field, project_id,
        )

    @router.delete("/{content_id}")
    def delete_agent_content(
        content_id: str, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.delete_agent_content(content_id, project_id)

    return router
