"""The versioned FLAPI package (tool) catalog."""

from fastapi import APIRouter, Depends

from app.api.models import PackageCreate, PackageInspect


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

    @router.post("/inspect")
    def inspect_package(payload: PackageInspect):
        data = payload.model_dump()
        root_id = data.pop("root_id")
        return context.service.inspect_tool(data, root_id)

    return router
