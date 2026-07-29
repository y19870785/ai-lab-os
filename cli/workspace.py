"""Visible Local Daily Profile workspace construction for CLI entrypoints."""

from __future__ import annotations

from core.system.settings import SystemSettings
from core.workspace.models import WorkspaceKey


def workspace_from_settings(
    settings: SystemSettings,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    namespace: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
    trace_id: str = "cli",
) -> WorkspaceKey:
    """Build a complete WorkspaceKey from visible profile values and overrides."""

    return WorkspaceKey(
        tenant_id=tenant_id or settings.workspace_tenant_id,
        workspace_id=workspace_id or settings.workspace_id,
        namespace=namespace or settings.workspace_namespace,
        session_id=session_id or settings.workspace_session_id,
        agent_id=agent_id or settings.workspace_agent_id,
        trace_id=trace_id,
    )
