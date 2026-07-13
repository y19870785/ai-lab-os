"""Knowledge API —— 知识问答路由。"""
from fastapi import APIRouter
from api.models import ChatRequest, ChatResponse
from api.dependencies import get_runtime
from applications.models import ApplicationRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/ask", response_model=ChatResponse)
async def ask(req: ChatRequest):
    """知识问答。"""
    runtime = get_runtime()
    app_req = ApplicationRequest(
        application_name="ceo-assistant",
        user_input=req.user_input,
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer, status=resp.status,
        mode=resp.mode, trace_id=resp.trace_id, latency_ms=resp.latency_ms,
    )
