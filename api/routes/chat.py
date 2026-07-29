"""Chat route."""

# ruff: noqa: B008

import uuid

from fastapi import APIRouter, Depends, Header, Request

from api.dependencies import get_runtime
from api.models import ChatRequest, ChatResponse
from api.workspace import workspace_from_request
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
    runtime: ApplicationRuntime = Depends(get_runtime),
):
    request_key = (
        idempotency_key.strip()
        or req.idempotency_key.strip()
        or uuid.uuid4().hex
    )
    app_req = ApplicationRequest(
        application_name=req.application_name,
        user_input=req.user_input,
        workspace_key=workspace_from_request(request, session_id=req.session_id),
        metadata={"idempotency_key": request_key},
    )
    resp = await runtime.execute(app_req)
    return ChatResponse(
        answer=resp.answer,
        status=resp.status,
        mode=resp.mode,
        trace_id=resp.trace_id,
        latency_ms=resp.latency_ms,
        metadata=resp.metadata,
    )
