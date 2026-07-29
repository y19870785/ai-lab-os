"""Shared request-to-WorkspaceKey construction for protected API entrypoints."""

from __future__ import annotations

from fastapi import Request

from core.workspace.models import WorkspaceKey


def workspace_from_request(
    request: Request,
    *,
    session_id: str | None = None,
    agent_id: str | None = None,
) -> WorkspaceKey:
    """Build one complete WorkspaceKey from validated request context."""

    resolved_session = (
        session_id.strip()
        if session_id is not None and session_id.strip()
        else getattr(request.state, "session_id", "")
    )
    resolved_agent = (
        agent_id.strip()
        if agent_id is not None and agent_id.strip()
        else getattr(request.state, "agent_id", "")
    )
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        session_id=resolved_session,
        agent_id=resolved_agent,
        trace_id=getattr(request.state, "trace_id", ""),
    )
