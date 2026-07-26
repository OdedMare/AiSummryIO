"""Workflow drafting, planning, publishing, and dry runs."""

from fastapi import APIRouter, Depends

from app.api.models import DryRunCreate, WorkflowCreate, WorkflowPlanCreate


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/workflows", tags=["workflows"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def workflows():
        return context.repository.list_workflows()

    @router.post("")
    def create_workflow(payload: WorkflowCreate):
        return context.repository.create_workflow(payload.model_dump())

    @router.post("/plan")
    def plan_workflow(payload: WorkflowPlanCreate):
        return context.service.plan_workflow(payload.prompt)

    @router.post("/{workflow_id}/publish")
    def publish_workflow(workflow_id: str):
        return context.repository.publish_workflow(workflow_id)

    @router.post("/{workflow_id}/dry-run")
    def dry_run(workflow_id: str, payload: DryRunCreate):
        return context.service.dry_run(workflow_id, payload.root_id)

    return router
