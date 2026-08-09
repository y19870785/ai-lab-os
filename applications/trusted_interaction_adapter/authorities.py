"""Fail-closed authority ports for Shell identity and operation policy."""

from __future__ import annotations

from typing import Any, Protocol

from applications.trusted_interaction_adapter.models import (
    ResolvedOperationPlan,
    ResolvedShellContext,
    ShellAssertion,
)
from core.errors import ErrorCategory, FailureException, FailureInfo


class ShellBindingResolver(Protocol):
    async def resolve(self, assertion: ShellAssertion) -> ResolvedShellContext: ...


class OperationPolicyResolver(Protocol):
    async def resolve(
        self,
        *,
        context: ResolvedShellContext,
        requested_operation: str,
        parameters: dict[str, Any],
        trace_id: str,
    ) -> ResolvedOperationPlan: ...


def _unavailable(code: str, operation: str, trace_id: str, message: str) -> None:
    raise FailureException(
        FailureInfo(
            code=code,
            category=ErrorCategory.PERMISSION_DENIED,
            message=message,
            component="trusted_interaction_adapter",
            operation=operation,
            retryable=False,
            trace_id=trace_id,
        )
    )


class DisabledShellBindingResolver:
    """Production default: Shell assertions never become authoritative identity."""

    async def resolve(self, assertion: ShellAssertion) -> ResolvedShellContext:
        trace_id = assertion.correlation.get("trace_id", "")
        _unavailable(
            "interaction_adapter.identity_binding_unavailable",
            "identity_binding",
            trace_id,
            "No authoritative Shell identity and Workspace binding is configured",
        )


class DisabledOperationPolicyResolver:
    """Production default: no requested operation is authorized by Shell text."""

    async def resolve(
        self,
        *,
        context: ResolvedShellContext,
        requested_operation: str,
        parameters: dict[str, Any],
        trace_id: str,
    ) -> ResolvedOperationPlan:
        _unavailable(
            "interaction_adapter.operation_policy_unavailable",
            "operation_policy",
            trace_id,
            "No authoritative operation policy resolver is configured",
        )
