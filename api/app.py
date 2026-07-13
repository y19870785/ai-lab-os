"""AI-Lab REST API —— FastAPI 应用。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import health, chat, applications, tasks, workflows
from api.routes import work_logs, decisions, brief, knowledge
from api.middleware import tracing, error_handler, context as ctx_mw

app = FastAPI(
    title="AI-Lab API",
    version="0.32.4",
    description="AI-Lab Application Platform REST API - CEO Assistant",
)

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Custom middleware
app.add_middleware(tracing.TracingMiddleware)
app.add_middleware(ctx_mw.ContextMiddleware)
app.add_middleware(error_handler.ErrorHandlerMiddleware)

# Routes
app.include_router(health.router)
app.include_router(applications.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(workflows.router)
app.include_router(work_logs.router)
app.include_router(decisions.router)
app.include_router(brief.router)
app.include_router(knowledge.router)

# Startup / Shutdown
@app.on_event("startup")
async def startup():
    from api.dependencies import get_runtime
    runtime = get_runtime()
    await runtime.initialize()

@app.on_event("shutdown")
async def shutdown():
    from api.dependencies import get_runtime
    runtime = get_runtime()
    await runtime.shutdown()
