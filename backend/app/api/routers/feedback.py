"""User feedback on a finished run."""

from fastapi import APIRouter, Depends

from app.api.models import FeedbackCreate


def build(context) -> APIRouter:
    router = APIRouter(tags=["feedback"])

    @router.post("/feedback")
    def feedback(
        payload: FeedbackCreate,
        session_id: str = Depends(context.user_session),
    ):
        run = context.repository.get_run(payload.run_id)
        context.repository.get_conversation(run["conversation_id"], session_id)
        return context.repository.save_feedback(session_id, payload.model_dump())

    return router
