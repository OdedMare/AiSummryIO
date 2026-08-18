"""Session-owned project workspaces and their capability assignments."""

from fastapi import APIRouter, Depends, Response

from app.api.models import ProjectCreate


def build(context) -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])

    @router.get("")
    def projects(
        response: Response, session_id: str = Depends(context.user_session)
    ):
        context.set_session_cookie(response, session_id)
        return context.repository.list_projects(session_id)

    @router.get("/{project_id}")
    def project(
        project_id: str, session_id: str = Depends(context.user_session)
    ):
        return context.repository.get_project(project_id, session_id)

    @router.post("")
    def create_project(
        payload: ProjectCreate,
        response: Response,
        session_id: str = Depends(context.user_session),
    ):
        context.set_session_cookie(response, session_id)
        return context.repository.create_project(
            session_id, payload.model_dump()
        )

    @router.put("/{project_id}")
    def update_project(
        project_id: str,
        payload: ProjectCreate,
        session_id: str = Depends(context.user_session),
    ):
        return context.repository.update_project(
            project_id, session_id, payload.model_dump()
        )

    @router.delete("/{project_id}")
    def delete_project(
        project_id: str, session_id: str = Depends(context.user_session)
    ):
        return context.repository.delete_project(project_id, session_id)

    return router
