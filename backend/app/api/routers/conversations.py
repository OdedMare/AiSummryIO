"""Conversation history and the user-selectable Skill catalog."""

from fastapi import APIRouter, Depends, Response


def build(context) -> APIRouter:
    router = APIRouter(tags=["conversations"])

    @router.get("/conversations")
    def conversations(
        response: Response, session_id: str = Depends(context.user_session)
    ):
        context.set_session_cookie(response, session_id)
        return context.repository.list_conversations(session_id)

    @router.get("/conversations/{conversation_id}")
    def conversation(
        conversation_id: str, session_id: str = Depends(context.user_session)
    ):
        return context.repository.get_conversation(conversation_id, session_id)

    @router.get("/skills")
    def summary_skills():
        return context.repository.list_summary_skills()

    return router
