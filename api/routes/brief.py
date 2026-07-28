"""Brief API —— 每日简报路由。"""
from fastapi import APIRouter, Depends, Request

from api.dependencies import get_runtime
from api.models import ChatResponse
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime
from core.workspace.models import WorkspaceKey

router = APIRouter(prefix="/brief", tags=["brief"])

@router.get("", response_model=ChatResponse)
async def get_brief(
    request: Request,
    runtime: ApplicationRuntime = Depends(get_runtime),  # noqa: B008
):
    """获取每日简报。"""
    app_req = ApplicationRequest(
        application_name="ceo-assistant",
        user_input="今日简报",
        workspace_key=WorkspaceKey(
            tenant_id=getattr(request.state, "tenant_id", "default"),
            workspace_id=getattr(request.state, "workspace_id", "default"),
            namespace=getattr(request.state, "namespace", "default"),
            trace_id=getattr(request.state, "trace_id", ""),
        ),
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer, status=resp.status,
        mode=resp.mode, trace_id=resp.trace_id, latency_ms=resp.latency_ms,
        metadata=resp.metadata,
    )
