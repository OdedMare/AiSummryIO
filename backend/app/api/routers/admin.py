"""FDE authorization probe, live settings, and the review queue."""

from fastapi import APIRouter, Depends

from app.api.models import ModelsProbeRequest


def build(context) -> APIRouter:
    router = APIRouter(tags=["admin"])
    guard = [Depends(context.admin_dependency)]

    @router.get("/admin/session", dependencies=guard)
    def admin_session():
        return {"authenticated": True}

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

    # Overrides let the settings panel test a base URL / API key typed in
    # the form BEFORE saving it. Empty or masked = fall back to the saved
    # value, matching LocatoAI.
    @router.post("/models", dependencies=guard)
    def probe_models(body: ModelsProbeRequest):
        return {"models": context.llm.list_models(
            base_url_override=body.override("llm_base_url"),
            api_key_override=body.override("openai_api_key"),
        )}

    @router.get("/review-queue", dependencies=guard)
    def review_queue():
        return context.repository.review_queue()

    return router
