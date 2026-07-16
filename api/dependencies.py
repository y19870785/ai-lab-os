"""FastAPI dependencies backed by the lifespan-owned SystemContainer."""

from fastapi import Depends, Request

from applications.runtime import ApplicationRuntime
from applications.security import Authenticator
from core.errors import FailureException
from core.system.container import SystemContainer
from core.system.exceptions import ServiceUnavailableError


def _get_system_unguarded(request: Request) -> SystemContainer:
    system = getattr(request.app.state, "system", None)
    if system is None:
        raise ServiceUnavailableError("AI-Lab system is not initialized")
    return system


def get_system(request: Request) -> SystemContainer:
    system = _get_system_unguarded(request)
    system.ensure_accepting_work()
    return system


def get_runtime(system: SystemContainer = Depends(get_system)) -> ApplicationRuntime:
    """Resolve Runtime after API admission; execute() closes the race window."""
    return system.application_runtime


def require_auth(request: Request) -> None:
    """Fail with 401 when the request lacks a valid Bearer token.

    Intended as a router-level dependency via include_router(..., dependencies=[Depends(require_auth)]).
    """
    sec_cfg = getattr(request.app.state, "api_security", None)
    if sec_cfg is None:
        from core.errors import FailureInfo, ErrorCategory
        raise FailureException(FailureInfo(
            code="api.auth.not_configured",
            category=ErrorCategory.NOT_CONFIGURED,
            message="API authentication is not configured",
            component="api.auth",
            operation="validate_bearer",
            retryable=False,
        ))
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        authenticator = Authenticator(sec_cfg)
    result = authenticator.validate_from_request(request)
    if not result.is_valid and result.failure is not None:
        raise FailureException(result.failure)
