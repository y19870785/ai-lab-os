"""Knowledge API —— 知识问答路由。"""
from fastapi import APIRouter, Depends
from api.models import ChatRequest, ChatResponse
from api.dependencies import get_runtime
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/ask", response_model=ChatResponse)
async def ask(
    req: ChatRequest,
    runtime: ApplicationRuntime = Depends(get_runtime),
):
    """知识问答。"""
    app_req = ApplicationRequest(
        application_name="ceo-assistant",
        user_input=req.user_input,
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer, status=resp.status,
        mode=resp.mode, trace_id=resp.trace_id, latency_ms=resp.latency_ms,
    )
