"""UserTask-local workspace normalization and ownership helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.workspace.models import WorkspaceKey

DEFAULT_WORKSPACE_IDENTITY = ("default", "default", "default")


def normalize_workspace_key(workspace_key: WorkspaceKey) -> WorkspaceKey:
    """Normalize empty request-scope components without changing global semantics."""

    return workspace_key.model_copy(
        update={
            "tenant_id": str(workspace_key.tenant_id or "").strip() or "default",
            "workspace_id": str(workspace_key.workspace_id or "").strip() or "default",
            "namespace": str(workspace_key.namespace or "").strip() or "default",
        }
    )


def workspace_identity(workspace_key: WorkspaceKey) -> tuple[str, str, str]:
    normalized = normalize_workspace_key(workspace_key)
    return (
        normalized.tenant_id,
        normalized.workspace_id,
        normalized.namespace,
    )


def canonical_workspace_metadata(workspace_key: WorkspaceKey) -> dict[str, str]:
    tenant_id, workspace_id, namespace = workspace_identity(workspace_key)
    return {
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "namespace": namespace,
    }


def workspace_key_from_evidence(
    value: Any,
    *,
    trace_id: str = "",
) -> WorkspaceKey:
    """Use only complete trusted evidence; incomplete legacy data belongs to default."""

    if isinstance(value, Mapping):
        parts = tuple(value.get(key) for key in DEFAULT_WORKSPACE_KEYS)
        if all(isinstance(part, str) and part.strip() for part in parts):
            return WorkspaceKey(
                tenant_id=parts[0],
                workspace_id=parts[1],
                namespace=parts[2],
                trace_id=trace_id,
            )
    return WorkspaceKey(
        tenant_id="default",
        workspace_id="default",
        namespace="default",
        trace_id=trace_id,
    )


DEFAULT_WORKSPACE_KEYS = ("tenant_id", "workspace_id", "namespace")
