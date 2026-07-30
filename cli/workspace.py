"""Visible Local Daily Profile workspace construction for CLI entrypoints."""

from __future__ import annotations

import uuid

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.settings import SystemSettings
from core.workspace.models import WorkspaceKey


def _workspace_value(
    *,
    name: str,
    override: str | None,
    profile_default: str,
    trace_id: str,
) -> str:
    if override is None:
        return profile_default
    value = override.strip()
    if value:
        return value
    raise FailureException(FailureInfo(
        code="workspace.cli_override_invalid",
        category=ErrorCategory.VALIDATION,
        message=f"CLI workspace override {name} must not be blank",
        component="cli.workspace",
        operation="construct",
        trace_id=trace_id,
        retryable=False,
        details={"field": name},
    ))


def workspace_from_settings(
    settings: SystemSettings,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    namespace: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
    trace_id: str | None = None,
) -> WorkspaceKey:
    """Build a complete key; every independent CLI request gets a fresh trace."""

    request_trace = trace_id or uuid.uuid4().hex
    return WorkspaceKey(
        tenant_id=_workspace_value(
            name="tenant_id",
            override=tenant_id,
            profile_default=settings.workspace_tenant_id,
            trace_id=request_trace,
        ),
        workspace_id=_workspace_value(
            name="workspace_id",
            override=workspace_id,
            profile_default=settings.workspace_id,
            trace_id=request_trace,
        ),
        namespace=_workspace_value(
            name="namespace",
            override=namespace,
            profile_default=settings.workspace_namespace,
            trace_id=request_trace,
        ),
        session_id=_workspace_value(
            name="session_id",
            override=session_id,
            profile_default=settings.workspace_session_id,
            trace_id=request_trace,
        ),
        agent_id=_workspace_value(
            name="agent_id",
            override=agent_id,
            profile_default=settings.workspace_agent_id,
            trace_id=request_trace,
        ),
        trace_id=request_trace,
    )
