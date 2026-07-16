"""Context middleware —— 构建 ApplicationContext。"""
from starlette.middleware.base import BaseHTTPMiddleware

class ContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Attach workspace context from headers or defaults
        request.state.tenant_id = request.headers.get("X-Tenant-ID", "default")
        request.state.workspace_id = request.headers.get("X-Workspace-ID", "default")
        request.state.namespace = request.headers.get("X-Namespace", "default")
        return await call_next(request)
