"""Shared persistent Evaluation batches."""

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.api.evaluation_excel import evaluation_workbook, read_root_ids
from app.api.models import EvaluationCreate, EvaluationReview


def build(context) -> APIRouter:
    router = APIRouter(tags=["evaluations"])

    @router.get("/evaluations")
    def evaluations():
        return context.repository.list_evaluation_batches()

    @router.post("/evaluations", status_code=201)
    def create_evaluation(
        payload: EvaluationCreate,
        response: Response,
        session_id: str = Depends(context.user_session),
    ):
        if payload.project_id:
            context.repository.get_project(payload.project_id, session_id)
        batch = context.repository.create_evaluation_batch(
            session_id, payload.model_dump(), payload.root_ids
        )
        context.set_session_cookie(response, session_id)
        context.evaluations.notify()
        return batch

    @router.post("/evaluations/import")
    async def import_evaluation(request: Request):
        return read_root_ids(await request.body())

    @router.get("/evaluations/{batch_id}")
    def evaluation(batch_id: str):
        return context.repository.get_evaluation_batch(batch_id)

    @router.get("/evaluations/{batch_id}/cases")
    def evaluation_cases(
        batch_id: str,
        status: Literal[
            "", "pending", "queued", "running", "completed", "partial",
            "failed", "stopped",
        ] = "",
        search: str = Query("", max_length=1000),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        return context.repository.list_evaluation_cases(
            batch_id, status, search.strip(), offset, limit
        )

    @router.get("/evaluations/{batch_id}/cases/{case_id}")
    def evaluation_case(batch_id: str, case_id: str):
        return context.repository.get_evaluation_case(batch_id, case_id)

    @router.put("/evaluations/{batch_id}/cases/{case_id}/review")
    def review_evaluation_case(
        batch_id: str, case_id: str, payload: EvaluationReview
    ):
        return context.repository.update_evaluation_review(
            batch_id, case_id, payload.rating, payload.comment
        )

    @router.post("/evaluations/{batch_id}/pause")
    def pause_evaluation(batch_id: str):
        batch = context.repository.change_evaluation_status(
            batch_id, "pausing", ("running",)
        )
        context.evaluations.notify()
        return batch

    @router.post("/evaluations/{batch_id}/resume")
    def resume_evaluation(batch_id: str):
        batch = context.repository.change_evaluation_status(
            batch_id, "running", ("paused",)
        )
        context.evaluations.notify()
        return batch

    @router.post("/evaluations/{batch_id}/stop")
    def stop_evaluation(batch_id: str):
        batch = context.repository.change_evaluation_status(
            batch_id, "stopping", ("running", "pausing", "paused")
        )
        context.evaluations.notify()
        return batch

    @router.post("/evaluations/{batch_id}/retry-failed", status_code=201)
    def retry_failed(
        batch_id: str,
        response: Response,
        session_id: str = Depends(context.user_session),
    ):
        source = context.repository.get_evaluation_batch(batch_id)
        root_ids = context.repository.failed_evaluation_root_ids(batch_id)
        if not root_ids:
            raise ValueError("אין תוצאות שנכשלו להרצה חוזרת")
        batch = context.repository.create_evaluation_batch(
            session_id,
            {
                "label": source["label"] + " · ניסיון חוזר",
                "project_id": source.get("project_id"),
                "question": source["question"],
                "skill_keys": source["skill_keys"],
                "agent_keys": source["agent_keys"],
                "cooldown_seconds": source["cooldown_seconds"],
            },
            root_ids,
        )
        context.set_session_cookie(response, session_id)
        context.evaluations.notify()
        return batch

    @router.get("/evaluations/{batch_id}/export")
    def export_evaluation(batch_id: str):
        batch = context.repository.get_evaluation_batch(batch_id)
        rows = context.repository.evaluation_export_rows(batch_id)
        data = evaluation_workbook(batch, rows)
        headers = {
            "Content-Disposition": 'attachment; filename="evaluation-%s.xlsx"'
            % batch_id,
        }
        return StreamingResponse(
            BytesIO(data),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers=headers,
        )

    @router.delete("/evaluations/{batch_id}")
    def delete_evaluation(batch_id: str):
        return context.repository.delete_evaluation_batch(batch_id)

    return router
