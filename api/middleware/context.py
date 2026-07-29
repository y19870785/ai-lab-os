"""Validate workspace headers and build the request context."""

from starlette.middleware.base import BaseHTTPMiddleware

from core.errors import ErrorCategory, FailureException, FailureInfo

_WORKSPACE_HEADERS = {
    "X-Tenant-ID": ("tenant_id", "default"),
    "X-Workspace-ID": ("workspace_id", "default"),
    "X-Namespace": ("namespace", "default"),
    "X-Session-ID": ("session_id", ""),
    "X-Agent-ID": ("agent_id", ""),
}


class ContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        defaults = getattr(request.app.state, "workspace_defaults", {})
        for header, (attribute, fallback) in _WORKSPACE_HEADERS.items():
            if header in request.headers:
                value = request.headers[header].strip()
                if not value:
                    raise FailureException(FailureInfo(
                        code="workspace.header_invalid",
                        category=ErrorCategory.VALIDATION,
                        message=f"{header} must not be blank",
                        component="api.workspace",
                        operation="resolve",
                        retryable=False,
                        details={"header": header},
                    ))
            else:
                value = str(defaults.get(attribute, fallback)).strip()
            setattr(request.state, attribute, value)
        return await call_next(request)
