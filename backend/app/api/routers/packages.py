"""The FLAPI package (tool) catalog."""

from fastapi import APIRouter, Depends

from app.api.models import PackageCreate, PackageInspect, ToolPlanChatCreate


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/packages", tags=["packages"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def packages(
        project_id: str, session_id: str = Depends(context.user_session)
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.list_packages(project_id)

    @router.post("")
    def create_package(
        payload: PackageCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.create_package(payload.model_dump(), project_id)

    @router.put("/{package_id}")
    def update_package(
        package_id: str, payload: PackageCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.update_package(
            package_id, payload.model_dump(), project_id
        )

    @router.post("/inspect")
    def inspect_package(
        payload: PackageInspect, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        data = payload.model_dump()
        root_id = data.pop("root_id")
        return context.service.inspect_tool(data, root_id)

    @router.delete("/{package_id}")
    def delete_package(
        package_id: str, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.repository.delete_package(package_id, project_id)

    @router.post("/plan-chat")
    def plan_tool_chat(
        payload: ToolPlanChatCreate, project_id: str,
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_project(project_id, session_id)
        return context.service.plan_tool_chat(
            [item.model_dump() for item in payload.messages],
            payload.draft, payload.inspection, payload.focus_field, project_id,
        )

    return router
