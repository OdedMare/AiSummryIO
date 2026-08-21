"""Workflow drafting, planning, and dry runs."""

from fastapi import APIRouter, Depends

from app.api.models import DryRunCreate, PlanChatCreate, WorkflowCreate


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/workflows", tags=["workflows"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def workflows(
        project_id: str, session_id: str = Depends(context.user_session)
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.list_workflows(project_id)

    @router.post("")
    def create_workflow(
        payload: WorkflowCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.create_workflow(payload.model_dump(), project_id)

    @router.put("/{workflow_id}")
    def update_workflow(
        workflow_id: str, payload: WorkflowCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.update_workflow(
            workflow_id, payload.model_dump(), project_id
        )

    @router.post("/plan-chat")
    def plan_workflow_chat(
        payload: PlanChatCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.plan_workflow_chat(
            [item.model_dump() for item in payload.messages], payload.draft,
            payload.focus_field, project_id,
        )

    @router.delete("/{workflow_id}")
    def delete_workflow(
        workflow_id: str, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.delete_workflow(workflow_id, project_id)

    @router.post("/{workflow_id}/dry-run")
    def dry_run(
        workflow_id: str, payload: DryRunCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.dry_run(workflow_id, payload.root_id, project_id)

    return router
