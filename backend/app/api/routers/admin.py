"""FDE authentication, live settings, and the review queue."""

from fastapi import APIRouter, Depends, Response

from app.api.auth import login
from app.api.models import AdminLogin


def build(context) -> APIRouter:
    router = APIRouter(tags=["admin"])
    guard = [Depends(context.admin_dependency)]

    @router.post("/admin/login")
    def admin_login(payload: AdminLogin, response: Response):
        token = login(context.store, payload.password)
        response.set_cookie(
            "aisummry_admin", token, httponly=True, samesite="strict",
            max_age=12 * 60 * 60,
        )
        return {"authenticated": True}

    @router.get("/admin/session", dependencies=guard)
    def admin_session():
        return {"authenticated": True}

    @router.delete("/admin/session")
    def admin_logout(response: Response):
        response.delete_cookie("aisummry_admin")
        return {"authenticated": False}

    @router.get("/settings", dependencies=guard)
    def get_settings():
        return context.store.public()

    @router.put("/settings", dependencies=guard)
    def update_settings(patch: dict):
        context.store.update(patch)
        return context.store.public()

    @router.get("/models", dependencies=guard)
    def models():
        return {"models": context.llm.list_models()}

    @router.get("/review-queue", dependencies=guard)
    def review_queue():
        return context.repository.review_queue()

    return router
