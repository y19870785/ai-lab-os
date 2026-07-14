"""Decisions API —— 决策记录路由。"""
from fastapi import APIRouter, Depends
from api.models import ChatRequest, ChatResponse
from api.dependencies import get_runtime
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime

router = APIRouter(prefix="/decisions", tags=["decisions"])

@router.post("", response_model=ChatResponse)
async def create_decision(
    req: ChatRequest,
    runtime: ApplicationRuntime = Depends(get_runtime),
):
    """记录决策。"""
    app_req = ApplicationRequest(
        application_name="ceo-assistant",
        user_input=req.user_input,
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer, status=resp.status,
        mode=resp.mode, trace_id=resp.trace_id, latency_ms=resp.latency_ms,
    )
