"""Context middleware —— 构建 ApplicationContext。"""
from starlette.middleware.base import BaseHTTPMiddleware


class ContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        defaults = getattr(request.app.state, "workspace_defaults", {})
        request.state.tenant_id = request.headers.get(
            "X-Tenant-ID", defaults.get("tenant_id", "default")
        )
        request.state.workspace_id = request.headers.get(
            "X-Workspace-ID", defaults.get("workspace_id", "default")
        )
        request.state.namespace = request.headers.get(
            "X-Namespace", defaults.get("namespace", "default")
        )
        request.state.session_id = request.headers.get(
            "X-Session-ID", defaults.get("session_id", "")
        )
        request.state.agent_id = request.headers.get(
            "X-Agent-ID", defaults.get("agent_id", "")
        )
        return await call_next(request)
