"""Summary creation and run status.

A summary is scoped by an identifier, by an area drawn on the map, or by
both — see ``SummaryCreate``. Execution stays asynchronous because a FLAPI
package can run for minutes; ``wait`` lets a programmatic client block for a
bounded time instead of writing its own poll loop.
"""

import time

from fastapi import APIRouter, Depends, Query, Response

from app.api.models import FollowUpCreate, SummaryCreate

# Bounds the synchronous convenience path. A caller wanting longer should poll
# the run, which is what the parameter degrades to on timeout.
MAX_WAIT_SECONDS = 300
_POLL_INTERVAL_SECONDS = 0.5
_FINISHED = ("completed", "partial", "failed")


def build(context) -> APIRouter:
    router = APIRouter(tags=["summaries"])

    @router.post("/summaries", status_code=202)
    def create_summary(
        payload: SummaryCreate,
        response: Response,
        wait: float = Query(
            0, ge=0, le=MAX_WAIT_SECONDS,
            description="Seconds to wait for the run to finish. 0 returns immediately.",
        ),
        session_id: str = Depends(context.user_session),
    ):
        conversation = context.repository.create_conversation(
            session_id, payload.root_id,
            payload.boundaries.model_dump() if payload.boundaries else None,
        )
        run = context.repository.create_run(
            conversation["id"], payload.question, "full", payload.skill_keys
        )
        context.jobs.submit(run["id"])
        context.set_session_cookie(response, session_id)
        run = _await_run(context, run, wait, response)
        return {"conversation": conversation, "run": run}

    @router.post("/conversations/{conversation_id}/messages", status_code=202)
    def follow_up(
        conversation_id: str,
        payload: FollowUpCreate,
        response: Response,
        wait: float = Query(0, ge=0, le=MAX_WAIT_SECONDS),
        session_id: str = Depends(context.user_session),
    ):
        context.repository.get_conversation(conversation_id, session_id)
        run = context.repository.create_run(
            conversation_id, payload.question, "follow_up", payload.skill_keys
        )
        context.jobs.submit(run["id"])
        context.set_session_cookie(response, session_id)
        return _await_run(context, run, wait, response)

    @router.get("/runs/{run_id}")
    def run_status(run_id: str, session_id: str = Depends(context.user_session)):
        return _authorized_run(context, run_id, session_id)

    @router.get("/runs/{run_id}/evidence")
    def run_evidence(
        run_id: str, session_id: str = Depends(context.user_session)
    ):
        _authorized_run(context, run_id, session_id)
        return context.repository.run_evidence(run_id)

    return router


def _authorized_run(context, run_id: str, session_id: str) -> dict:
    """Load a run only if it belongs to the caller's conversation."""
    run = context.repository.get_run(run_id)
    context.repository.get_conversation(run["conversation_id"], session_id)
    return run


def _await_run(context, run: dict, wait: float, response: Response) -> dict:
    """Poll the run until it finishes or ``wait`` elapses.

    Returns 200 with the finished run, or leaves the 202 in place and returns
    the unfinished run so the caller can keep polling. Waiting is opt-in, so
    the browser's existing behavior is unchanged.
    """
    if not wait:
        return run
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if run["status"] in _FINISHED:
            response.status_code = 200
            return run
        time.sleep(_POLL_INTERVAL_SECONDS)
        run = context.repository.get_run(run["id"])
    if run["status"] in _FINISHED:
        response.status_code = 200
    return run
