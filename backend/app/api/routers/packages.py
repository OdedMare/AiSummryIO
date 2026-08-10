"""The FLAPI package (tool) catalog."""

from fastapi import APIRouter, Depends

from app.api.models import PackageCreate, PackageInspect, ToolPlanChatCreate


def build(context) -> APIRouter:
    router = APIRouter(
        prefix="/packages", tags=["packages"],
        dependencies=[Depends(context.admin_dependency)],
    )

    @router.get("")
    def packages():
        return context.repository.list_packages()

    @router.post("")
    def create_package(payload: PackageCreate):
        return context.repository.create_package(payload.model_dump())

    @router.put("/{package_id}")
    def update_package(package_id: str, payload: PackageCreate):
        return context.repository.update_package(
            package_id, payload.model_dump()
        )

    @router.post("/inspect")
    def inspect_package(payload: PackageInspect):
        data = payload.model_dump()
        root_id = data.pop("root_id")
        return context.service.inspect_tool(data, root_id)

    @router.delete("/{package_id}")
    def delete_package(package_id: str):
        return context.repository.delete_package(package_id)

    @router.post("/plan-chat")
    def plan_tool_chat(payload: ToolPlanChatCreate):
        return context.service.plan_tool_chat(
            [item.model_dump() for item in payload.messages],
            payload.draft, payload.inspection, payload.focus_field,
        )

    return router
