"""Brief API —— 每日简报路由。"""
from fastapi import APIRouter, Depends
from api.models import ChatRequest, ChatResponse
from api.dependencies import get_runtime
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime

router = APIRouter(prefix="/brief", tags=["brief"])

@router.get("", response_model=ChatResponse)
async def get_brief(runtime: ApplicationRuntime = Depends(get_runtime)):
    """获取每日简报。"""
    app_req = ApplicationRequest(
        application_name="ceo-assistant",
        user_input="今日简报",
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer, status=resp.status,
        mode=resp.mode, trace_id=resp.trace_id, latency_ms=resp.latency_ms,
    )
