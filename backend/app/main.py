"""FastAPI composition root for users, persistent jobs, and FDE Studio."""

import json
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import make_dependencies
from app.api.routers import register
from app.api.routers.context import ApiContext
from app.bl.jobs import JobRunner
from app.bl.workflow_engine import SummaryService
from app.common.config.settings import Settings
from app.common.errors import AppError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.repository import Repository

env = Settings()
store = RuntimeSettingsStore(env)
repository = Repository(store)
llm = OpenAIJsonClient(store)
provider = FlapiProvider(store)
service = SummaryService(repository, provider, llm, store)
jobs = JobRunner(repository, service, store.get().max_parallel_workflows)

app = FastAPI(
    title="AiSummryIO",
    version="0.1.0",
    description=(
        "Evidence-backed Hebrew summaries by identifier or map area. "
        "Programmatic clients authenticate with the API token as "
        "`X-API-Key` or `Authorization: Bearer`."
    ),
)

admin_dependency, user_session, set_session_cookie = make_dependencies(store)

register(app, ApiContext(
    repository=repository,
    service=service,
    jobs=jobs,
    store=store,
    llm=llm,
    admin_dependency=admin_dependency,
    user_session=user_session,
    set_session_cookie=set_session_cookie,
))


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
y

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
