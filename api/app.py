"""AI-Lab REST API，由 FastAPI lifespan 持有唯一 SystemContainer。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import context as ctx_mw
from api.middleware import error_handler, tracing
from api.routes import applications, brief, chat, decisions, health, knowledge
from api.routes import tasks, work_logs, workflows
from core.system import SystemSettings, create_system, load_system_settings


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
        version="0.32.4",
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
