"""Conversation history and the user-selectable Skill catalog."""

from fastapi import APIRouter, Depends, Query, Response


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

    @router.get("/conversations/{conversation_id}/messages")
    def conversation_messages(
        conversation_id: str,
        limit: int = Query(20, ge=1, le=100),
        session_id: str = Depends(context.user_session),
    ):
        """The thread's finished turns, oldest first.

        Loaded first so an unknown conversation, or one belonging to another
        session, fails here rather than leaking its turns.
        """
        context.repository.get_conversation(conversation_id, session_id)
        return context.repository.conversation_history(conversation_id, limit)

    @router.get("/skills")
    def summary_skills():
        return context.repository.list_summary_skills()

    return router
