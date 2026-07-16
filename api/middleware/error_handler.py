"""Unified API failure responses without leaking internal stack details."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.models import APIErrorResponse
from core.errors import (
    ErrorCategory,
    FailureInfo,
    failure_from_exception,
    http_status_for_failure,
)


logger = logging.getLogger("ai-lab.api.errors")


def make_error_response(failure: FailureInfo) -> JSONResponse:
    body = APIErrorResponse(
        code=failure.code,
        message=failure.message,
        component=failure.component,
        retryable=failure.retryable,
        trace_id=failure.trace_id,
        details={} if failure.category == ErrorCategory.INTERNAL else failure.details,
    )
    headers = {"X-Trace-ID": failure.trace_id}
    if failure.category.value == "unauthenticated":
        headers["WWW-Authenticate"] = "Bearer"
    if failure.code.startswith("system.draining"):
        headers["Retry-After"] = "1"
    return JSONResponse(
        status_code=http_status_for_failure(failure),
        content=body.model_dump(mode="json"),
        headers=headers,
    )


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            trace_id = getattr(request.state, "trace_id", "") or uuid.uuid4().hex
            failure = failure_from_exception(
                exc,
                component="api",
                operation=f"{request.method.lower()} {request.url.path}",
                trace_id=trace_id,
                code="api.request.failed",
            )
            if failure.category == ErrorCategory.INTERNAL:
                logger.exception(
                    "api.request.failed",
                    extra={"trace_id": trace_id, "failure_code": failure.code},
                )
            else:
                logger.warning(
                    "api.request.rejected",
                    extra={"trace_id": trace_id, "failure_code": failure.code,
                           "category": failure.category.value},
                )
            return make_error_response(failure)
