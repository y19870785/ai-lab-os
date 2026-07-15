"""AI-Lab REST API，由 FastAPI lifespan 持有唯一 SystemContainer。"""

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import context as ctx_mw
from api.middleware import error_handler, tracing
from api.routes import applications, brief, chat, decisions, health, knowledge
from api.routes import tasks, work_logs, workflows
from core import __version__
from core.system import SystemSettings, create_system, load_system_settings
from core.errors import ErrorCategory, FailureInfo


def create_app(settings: SystemSettings | None = None) -> FastAPI:
    """Create an API app; tests may inject isolated settings."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        effective_settings = settings or load_system_settings()
        system = await create_system(effective_settings)
        await system.start()
        app.state.system = system
        try:
            yield
        finally:
            await system.shutdown()
            app.state.system = None

    api = FastAPI(
        title="AI-Lab API",
        version=__version__,
        description="AI-Lab Application Platform REST API - CEO Assistant",
        lifespan=lifespan,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.add_middleware(tracing.TracingMiddleware)
    api.add_middleware(ctx_mw.ContextMiddleware)
    api.add_middleware(error_handler.ErrorHandlerMiddleware)

    @api.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", "") or uuid.uuid4().hex
        issues = [
            {"location": list(item.get("loc", ())), "message": item.get("msg", ""),
             "type": item.get("type", "")}
            for item in exc.errors()
        ]
        failure = FailureInfo(
            code="api.request.validation_failed",
            category=ErrorCategory.VALIDATION,
            message="Request validation failed",
            component="api",
            operation=f"{request.method.lower()} {request.url.path}",
            retryable=False,
            trace_id=trace_id,
            cause_type=exc.__class__.__name__,
            details={"issues": issues},
        )
        return error_handler.make_error_response(failure)

    for router in (
        health.router,
        applications.router,
        chat.router,
        tasks.router,
        workflows.router,
        work_logs.router,
        decisions.router,
        brief.router,
        knowledge.router,
    ):
        api.include_router(router)
    return api


app = create_app()
