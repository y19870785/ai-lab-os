"""Shell-neutral request and response contracts for trusted interactions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.errors import FailureInfo
from core.workspace.models import WorkspaceKey

CONTRACT_VERSION = "trusted-interaction/v1"


class ShellAssertion(BaseModel):
    """Untrusted assertions supplied by a channel or replaceable Agent Shell."""

    model_config = ConfigDict(frozen=True)

    channel: str
    shell: str
    shell_session_id: str
    channel_identity: str
    asserted_workspace: str | None = None
    message_id: str = ""
    correlation: dict[str, str] = Field(default_factory=dict)


class ResolvedShellContext(BaseModel):
    """AI-Lab-authoritative identity and Workspace binding."""

    model_config = ConfigDict(frozen=True)

    workspace: WorkspaceKey
    actor_id: str
    binding_type: str
    binding_evidence_id: str


class ResolvedOperationPlan(BaseModel):
    """AI-Lab-authoritative operation and policy resolution."""

    model_config = ConfigDict(frozen=True)

    canonical_operation: str
    policy_reference: str
    risk_level: str
    normalized_parameters: dict[str, Any]
    mutation_summary: str
    safe_summary: str = ""
    target_object_id: str | None = None
    target_revision: int | None = None
    expected_external_effects: tuple[str, ...] = ()
    requires_confirmation: bool = True
    requires_approval: bool = False
    canonical_commit_required: bool = True
    preview_ttl_seconds: int = 900

    @property
    def preview_ttl(self) -> timedelta:
        return timedelta(seconds=self.preview_ttl_seconds)


class PreviewPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_id: str
    preview_revision: int
    status: str
    operation: str
    policy_reference: str
    risk_level: str
    normalized_parameters: dict[str, Any]
    mutation_summary: str
    expected_external_effects: tuple[str, ...]
    requires_confirmation: bool
    requires_approval: bool
    canonical_commit_required: bool
    expires_at: str


class AdapterResponse(BaseModel):
    """Transport-neutral projection; MCP success is never business success."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = CONTRACT_VERSION
    request_id: str
    trace_id: str
    interaction_id: str | None = None
    revision: int | None = None
    authoritative: bool = False
    lifecycle_state: str | None = None
    execution_status: str | None = None
    verification_status: str | None = None
    recovery_status: str | None = None
    available_operations: tuple[str, ...] = ()
    preview: PreviewPayload | None = None
    failure: FailureInfo | None = None
    final: bool = False
