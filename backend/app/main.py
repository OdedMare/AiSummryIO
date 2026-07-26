"""FastAPI composition root for users, persistent jobs, and FDE Studio."""

import json
import logging
import uuid
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.auth import (
    login, require_admin_token, session_signature, verify_session,
)
from app.bl.jobs import JobRunner
from app.bl.workflow_engine import SummaryService
from app.common.config.settings import Settings
from app.common.errors import AppError, AuthError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.flapi.provider import FlapiProvider
from app.models import (
    AdminLogin, AgentContentCreate, FeedbackCreate, FollowUpCreate,
    PackageCreate, SummaryCreate, WorkflowCreate,
)
from app.repository import Repository

env = Settings()
store = RuntimeSettingsStore(env)
repository = Repository(store)
llm = OpenAIJsonClient(store)
provider = FlapiProvider(store)
service = SummaryService(repository, provider, llm, store)
jobs = JobRunner(repository, service, store.get().max_parallel_workflows)
app = FastAPI(title="AiSummryIO", version="0.1.0")


@app.on_event("startup")
def startup():
    repository.initialize()
    jobs.recover()


@app.exception_handler(AppError)
async def app_error_handler(_request, exc):
    return JSONResponse(
        status_code=exc.status_code, content={"detail": str(exc)}
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.middleware("http")
async def request_log(request: Request, call_next):
    response = await call_next(request)
    record = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
    }
    logging.getLogger("aisummry.request").info("%s", record)
    try:
        path = Path(env.request_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as target:
            target.write(json.dumps(record) + "\n")
    except OSError:
        pass
    return response


def admin_dependency(
    aisummry_admin: str = Cookie(default=""),
):
    require_admin_token(store, aisummry_admin)


def user_session(
    aisummry_session: str = Cookie(default=""),
) -> str:
    if aisummry_session:
        try:
            return verify_session(store, aisummry_session)
        except AuthError:
            pass
    return str(uuid.uuid4())


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        "aisummry_session", session_signature(store, session_id),
        httponly=True, samesite="lax", max_age=30 * 24 * 60 * 60,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", **repository.health()}


@app.post("/api/summaries")
def create_summary(
    payload: SummaryCreate,
    response: Response,
    session_id: str = Depends(user_session),
):
    conversation = repository.create_conversation(
        session_id, payload.root_id
    )
    run = repository.create_run(
        conversation["id"], payload.question, "full"
    )
    jobs.submit(run["id"])
    set_session_cookie(response, session_id)
    return {"conversation": conversation, "run": run}


@app.post("/api/conversations/{conversation_id}/messages")
def follow_up(
    conversation_id: str,
    payload: FollowUpCreate,
    response: Response,
    session_id: str = Depends(user_session),
):
    repository.get_conversation(conversation_id, session_id)
    run = repository.create_run(
        conversation_id, payload.question, "follow_up"
    )
    jobs.submit(run["id"])
    set_session_cookie(response, session_id)
    return run


@app.get("/api/conversations")
def conversations(session_id: str = Depends(user_session)):
    return repository.list_conversations(session_id)


@app.get("/api/conversations/{conversation_id}")
def conversation(
    conversation_id: str, session_id: str = Depends(user_session)
):
    return repository.get_conversation(conversation_id, session_id)


@app.get("/api/runs/{run_id}")
def run_status(run_id: str, session_id: str = Depends(user_session)):
    run = repository.get_run(run_id)
    repository.get_conversation(run["conversation_id"], session_id)
    return run


@app.get("/api/runs/{run_id}/evidence")
def run_evidence(run_id: str, session_id: str = Depends(user_session)):
    run = repository.get_run(run_id)
    repository.get_conversation(run["conversation_id"], session_id)
    return repository.run_evidence(run_id)


@app.post("/api/feedback")
def feedback(
    payload: FeedbackCreate,
    session_id: str = Depends(user_session),
):
    run = repository.get_run(payload.run_id)
    repository.get_conversation(run["conversation_id"], session_id)
    return repository.save_feedback(session_id, payload.model_dump())


@app.post("/api/admin/login")
def admin_login(payload: AdminLogin, response: Response):
    token = login(store, payload.password)
    response.set_cookie(
        "aisummry_admin", token, httponly=True, samesite="strict",
        max_age=12 * 60 * 60,
    )
    return {"authenticated": True}


@app.get("/api/admin/session", dependencies=[Depends(admin_dependency)])
def admin_session():
    return {"authenticated": True}


@app.delete("/api/admin/session")
def admin_logout(response: Response):
    response.delete_cookie("aisummry_admin")
    return {"authenticated": False}


@app.get("/api/settings", dependencies=[Depends(admin_dependency)])
def get_settings():
    return store.public()


@app.put("/api/settings", dependencies=[Depends(admin_dependency)])
def update_settings(patch: dict):
    store.update(patch)
    return store.public()


@app.get("/api/models", dependencies=[Depends(admin_dependency)])
def models():
    return {"models": llm.list_models()}


@app.get("/api/packages", dependencies=[Depends(admin_dependency)])
def packages():
    return repository.list_packages()


@app.post("/api/packages", dependencies=[Depends(admin_dependency)])
def create_package(payload: PackageCreate):
    return repository.create_package(payload.model_dump())


@app.get("/api/workflows", dependencies=[Depends(admin_dependency)])
def workflows():
    return repository.list_workflows()


@app.post("/api/workflows", dependencies=[Depends(admin_dependency)])
def create_workflow(payload: WorkflowCreate):
    return repository.create_workflow(payload.model_dump())


@app.post(
    "/api/workflows/{workflow_id}/publish",
    dependencies=[Depends(admin_dependency)],
)
def publish_workflow(workflow_id: str):
    return repository.publish_workflow(workflow_id)


@app.post(
    "/api/workflows/{workflow_id}/dry-run",
    dependencies=[Depends(admin_dependency)],
)
def dry_run(workflow_id: str, payload: SummaryCreate):
    return service.dry_run(workflow_id, payload.root_id)


@app.get("/api/agent-content", dependencies=[Depends(admin_dependency)])
def agent_content():
    return repository.list_agent_content()


@app.post("/api/agent-content", dependencies=[Depends(admin_dependency)])
def create_agent_content(payload: AgentContentCreate):
    return repository.create_agent_content(payload.model_dump())


@app.post(
    "/api/agent-content/{content_id}/publish",
    dependencies=[Depends(admin_dependency)],
)
def publish_agent_content(content_id: str):
    return repository.publish_agent_content(content_id)


@app.get("/api/review-queue", dependencies=[Depends(admin_dependency)])
def review_queue():
    return repository.review_queue()
