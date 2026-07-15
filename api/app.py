"""AI-Lab REST API，由 FastAPI lifespan 持有唯一 SystemContainer。"""

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import context as ctx_mw
from api.middleware import error_handler, tracing
from api.routes import applications, brief, chat, decisions, health, knowledge
from api.routes import reminders, tasks, work_logs, workflows
from core import __version__
from core.system import SystemSettings, create_system, load_system_settings
from applications.security import ApiSecurityConfig, Authenticator
from core.errors import ErrorCategory, FailureInfo




def create_app(settings: SystemSettings | None = None) -> FastAPI:
    """Create an API app; tests may inject isolated settings.

    When called without explicit settings, defaults to auth-disabled for
    uvicorn module-level discovery.  Callers that want auth must pass
    settings with enable_api_auth=True and api_token set.
    """

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

    effective_settings = (
        settings
        or load_system_settings()
    )
    # Default to auth-disabled when no explicit settings are provided
    # Tests / production callers inject explicit settings.
    sec_cfg = ApiSecurityConfig.from_settings(
        auth_enabled=effective_settings.enable_api_auth,
        api_token=effective_settings.api_token,
        allowed_origins=list(effective_settings.api_allowed_origins),
        environment=effective_settings.environment,
    )

    cors_kwargs: dict = dict(allow_methods=["*"], allow_headers=["*"])
    if sec_cfg.allowed_origins:
        cors_kwargs["allow_origins"] = sec_cfg.allowed_origins
    else:
        cors_kwargs["allow_origins"] = []

    api = FastAPI(
        title="AI-Lab API",
        version=__version__,
        description="AI-Lab Application Platform REST API - CEO Assistant",
        lifespan=lifespan,
    )
    api.state.api_security = sec_cfg
    api.state.authenticator = Authenticator(sec_cfg)
    api.add_middleware(CORSMiddleware, **cors_kwargs)
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

    # Public: health, metrics (no auth)
    for router in (health.router,):
        api.include_router(router)

    # Protected: all business routes
    from api.dependencies import require_auth
    from fastapi import Depends
    for router in (
        applications.router,
        chat.router,
        tasks.router,
        reminders.router,
        workflows.router,
        work_logs.router,
        decisions.router,
        brief.router,
        knowledge.router,
    ):
        api.include_router(router, dependencies=[Depends(require_auth)])

    return api



# Lazy module-level app: create on first access, not at import time.
# Tests import from api.app for create_app(); uvicorn accesses api.app:app.
_app_instance = None

def __getattr__(name):
    if name == "app":
        global _app_instance
        if _app_instance is None:
            _app_instance = create_app()
        return _app_instance
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
