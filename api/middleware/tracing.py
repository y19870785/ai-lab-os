"""Tracing middleware —— 自动生成 trace_id。"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex)
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
