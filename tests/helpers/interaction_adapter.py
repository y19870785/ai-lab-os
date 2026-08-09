"""Deterministic test-only authorities for the Shell-neutral adapter."""

from __future__ import annotations

from typing import Any

from applications.trusted_interaction_adapter import (
    ResolvedOperationPlan,
    ResolvedShellContext,
    ShellAssertion,
)
from core.workspace.models import WorkspaceKey


class ReferenceShellBindingResolver:
    def __init__(
        self,
        *,
        tenant_id: str = "tenant-a",
        workspace_id: str = "workspace-a",
        namespace: str = "business",
        actor_id: str = "owner-a",
    ) -> None:
        self.context = ResolvedShellContext(
            workspace=WorkspaceKey(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                namespace=namespace,
                user_id=actor_id,
                trace_id="trace-adapter",
            ),
            actor_id=actor_id,
            binding_type="reference-test-only",
            binding_evidence_id="binding-evidence-1",
        )
        self.assertions: list[ShellAssertion] = []

    async def resolve(self, assertion: ShellAssertion) -> ResolvedShellContext:
        self.assertions.append(assertion)
        return self.context


class ReferenceOperationPolicyResolver:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []

    async def resolve(
        self,
        *,
        context: ResolvedShellContext,
        requested_operation: str,
        parameters: dict[str, Any],
        trace_id: str,
    ) -> ResolvedOperationPlan:
        self.requests.append((requested_operation, parameters))
        return ResolvedOperationPlan(
            canonical_operation="reference.noop",
            policy_reference="policy/reference-noop/v1",
            risk_level="low",
            normalized_parameters=parameters,
            mutation_summary="Reference no-op Preview",
            safe_summary="Reference no-op interaction",
            expected_external_effects=(),
            requires_confirmation=True,
            requires_approval=False,
            canonical_commit_required=False,
            preview_ttl_seconds=3600,
        )


def shell_assertion(*, shell: str = "reference-shell") -> ShellAssertion:
    return ShellAssertion(
        channel="reference-channel",
        shell=shell,
        shell_session_id="shell-session-1",
        channel_identity="channel-user-1",
        asserted_workspace="untrusted-workspace-claim",
        message_id="message-1",
        correlation={"request_id": "request-1", "trace_id": "trace-1"},
    )
