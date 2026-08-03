"""FastAPI composition root for users, persistent jobs, and FDE Studio."""

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.dependencies import make_dependencies
from app.api.routers import register
from app.api.routers.context import ApiContext
from app.api.validation_errors import format_validation_error
from app.bl.jobs import JobRunner
from app.bl.workflow_engine import SummaryService
from app.common.config.settings import Settings
from app.common.errors import AppError
from app.common.logging_setup import configure_logging, trace
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.repository import Repository

# Before anything else constructs a logger, so no start-up line is lost.
configure_logging()
_log = trace("api")

env = Settings()
store = RuntimeSettingsStore(env)
repository = Repository(store)
llm = OpenAIJsonClient(store)
provider = FlapiProvider(store)
service = SummaryService(repository, provider, llm, store)
jobs = JobRunner(repository, service, store.get().max_parallel_workflows)

app = FastAPI(
    title="SumOrAI",
    version="0.1.0",
    description=(
        "Evidence-backed Hebrew summaries by identifier or map area. "
        "The service is unauthenticated and expects to be reachable only "
        "from a trusted network."
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
async def app_error_handler(request, exc):
    _log.warning(
        "AppError %s %s -> %s: %s",
        request.method, request.url.path, exc.status_code, exc,
    )
    return JSONResponse(
        status_code=exc.status_code, content={"detail": str(exc)}
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    _log.warning(
        "ValueError %s %s -> 422: %s", request.method, request.url.path, exc,
    )
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc):
    """Log the full traceback for anything that reached here uncaught.

    Starlette otherwise returns a bare "Internal Server Error" with the
    traceback only on stderr, so the browser sees a 500 with no cause and the
    JSON body the client tries to parse is not JSON at all. Constraint
    violations from psycopg arrive here — the workflow-step foreign key being
    the known one — and the offending value is what identifies them.
    """
    _log.exception(
        "UNHANDLED %s %s -> 500 %s: %s",
        request.method, request.url.path, type(exc).__name__, exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "שגיאת שרת פנימית: %s: %s" % (type(exc).__name__, exc)
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, exc):
    """Return one Hebrew sentence instead of FastAPI's list of error objects.

    The default 422 body is ``detail: [{loc, msg, type}, ...]``, which any
    client joining it into a message renders as "[object Object]". Callers
    here only ever need to know which field was rejected and why.
    """
    return JSONResponse(
        status_code=422, content={"detail": format_validation_error(exc)}
    )


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.time()
    # Polling hits /api/runs/{id} every 1.5s; logging each one at INFO buries
    # everything else, so the poll is traced at DEBUG only.
    quiet = request.url.path.startswith("/api/runs/")
    if not quiet:
        _log.info("--> %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = time.time() - started
    record = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
    }
    _log.log(
        _response_level(response.status_code, elapsed, quiet),
        "<-- %s %s %s (%.2fs)",
        request.method, request.url.path, response.status_code, elapsed,
    )
    logging.getLogger("aisummry.request").debug("%s", record)
    try:
        path = Path(env.request_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as target:
            target.write(json.dumps(record) + "\n")
    except OSError:
        pass
    return response


def _response_level(status: int, elapsed: float, quiet: bool) -> int:
    """How loudly to report one response.

    A failure is always worth a line even on the polling route, and so is a
    slow success — a run poll that suddenly takes seconds is the first
    visible sign of a saturated worker pool.
    """
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    if elapsed >= 3.0:
        return logging.WARNING
    return logging.DEBUG if quiet else logging.INFO
