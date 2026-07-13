"""Error handler middleware —— 统一错误响应，不暴露内部堆栈。"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            trace_id = getattr(request.state, "trace_id", "")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "detail": str(e)[:200], "trace_id": trace_id},
            )
