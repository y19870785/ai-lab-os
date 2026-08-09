"""Shell-neutral orchestration over the canonical InteractionService boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from applications.trusted_interaction_adapter.authorities import (
    DisabledOperationPolicyResolver,
    DisabledShellBindingResolver,
    OperationPolicyResolver,
    ShellBindingResolver,
)
from applications.trusted_interaction_adapter.models import (
    AdapterResponse,
    ResolvedShellContext,
    ShellAssertion,
)
from applications.trusted_interaction_adapter.projection import (
    project_failure,
    project_status,
)
from core.errors import (
    ErrorCategory,
    FailureException,
    FailureInfo,
    failure_from_exception,
)
from core.interaction import InteractionService


class TrustedInteractionAdapter:
    """The only Shell-facing facade; all canonical writes stay in InteractionService."""

    def __init__(
        self,
        interaction_service: InteractionService,
        binding_resolver: ShellBindingResolver | None = None,
        policy_resolver: OperationPolicyResolver | None = None,
    ) -> None:
        self._interactions = interaction_service
        self._bindings = binding_resolver or DisabledShellBindingResolver()
        self._policies = policy_resolver or DisabledOperationPolicyResolver()

    @staticmethod
    def _correlation(assertion: ShellAssertion) -> tuple[str, str]:
        return (
            assertion.correlation.get("request_id") or assertion.message_id,
            assertion.correlation.get("trace_id", ""),
        )

    @staticmethod
    def _adapter_failure(
        *, code: str, operation: str, message: str, trace_id: str
    ) -> FailureException:
        return FailureException(
            FailureInfo(
                code=code,
                category=ErrorCategory.VALIDATION,
                message=message,
                component="trusted_interaction_adapter",
                operation=operation,
                retryable=False,
                trace_id=trace_id,
            )
        )

    async def _resolve(self, assertion: ShellAssertion) -> ResolvedShellContext:
        return await self._bindings.resolve(assertion)

    async def _respond(
        self,
        *,
        context: ResolvedShellContext,
        interaction_id: str,
        request_id: str,
        trace_id: str,
    ) -> AdapterResponse:
        status = await self._interactions.status(
            workspace=context.workspace,
            actor_id=context.actor_id,
            interaction_id=interaction_id,
        )
        view = await self._interactions.view(
            workspace=context.workspace,
            actor_id=context.actor_id,
            interaction_id=interaction_id,
        )
        return project_status(status, view, request_id=request_id, trace_id=trace_id)

    async def _guard(
        self,
        assertion: ShellAssertion,
        operation: Callable[[ResolvedShellContext, str, str], Awaitable[AdapterResponse]],
    ) -> AdapterResponse:
        request_id, trace_id = self._correlation(assertion)
        try:
            context = await self._resolve(assertion)
            return await operation(context, request_id, trace_id)
        except FailureException as exc:
            return project_failure(
                exc.failure,
                request_id=request_id,
                trace_id=trace_id,
                authoritative=not exc.failure.code.startswith("interaction_adapter."),
            )
        except Exception as exc:  # noqa: BLE001 - authority/adapter boundary
            failure = failure_from_exception(
                exc,
                component="trusted_interaction_adapter",
                operation="adapter",
                trace_id=trace_id,
                code="interaction_adapter.internal_failure",
            )
            return project_failure(
                failure, request_id=request_id, trace_id=trace_id
            )

    async def preview(
        self,
        *,
        assertion: ShellAssertion,
        requested_operation: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> AdapterResponse:
        async def action(
            context: ResolvedShellContext, request_id: str, trace_id: str
        ) -> AdapterResponse:
            plan = await self._policies.resolve(
                context=context,
                requested_operation=requested_operation,
                parameters=parameters,
                trace_id=trace_id,
            )
            if plan.preview_ttl_seconds <= 0:
                raise self._adapter_failure(
                    code="interaction_adapter.policy_invalid",
                    operation="preview",
                    message="Resolved preview expiry must be in the future",
                    trace_id=trace_id,
                )
            created = await self._interactions.create_interaction(
                workspace=context.workspace,
                actor_id=context.actor_id,
                operation=plan.canonical_operation,
                risk_level=plan.risk_level,
                policy_reference=plan.policy_reference,
                request_id=request_id,
                trace_id=trace_id,
                idempotency_key=f"{idempotency_key}:create",
                safe_summary=plan.safe_summary,
                correlation={
                    "channel": assertion.channel,
                    "shell": assertion.shell,
                    "shell_session_id": assertion.shell_session_id,
                    "message_id": assertion.message_id,
                    "binding_evidence_id": context.binding_evidence_id,
                    **assertion.correlation,
                },
            )
            await self._interactions.preview(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=created.interaction_id,
                expected_revision=created.revision,
                normalized_parameters=plan.normalized_parameters,
                mutation_summary=plan.mutation_summary,
                expires_in=plan.preview_ttl,
                idempotency_key=f"{idempotency_key}:preview",
                target_object_id=plan.target_object_id,
                target_revision=plan.target_revision,
                expected_external_effects=plan.expected_external_effects,
                requires_confirmation=plan.requires_confirmation,
                requires_approval=plan.requires_approval,
                canonical_commit_required=plan.canonical_commit_required,
            )
            return await self._respond(
                context=context,
                interaction_id=created.interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)

    async def modify(
        self,
        *,
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        requested_operation: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> AdapterResponse:
        async def action(
            context: ResolvedShellContext, request_id: str, trace_id: str
        ) -> AdapterResponse:
            plan = await self._policies.resolve(
                context=context,
                requested_operation=requested_operation,
                parameters=parameters,
                trace_id=trace_id,
            )
            current = await self._interactions.status(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=interaction_id,
            )
            if current.interaction.operation != plan.canonical_operation:
                raise self._adapter_failure(
                    code="interaction_adapter.operation_mismatch",
                    operation="modify",
                    message="Resolved operation does not match the canonical Interaction",
                    trace_id=trace_id,
                )
            await self._interactions.preview(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                normalized_parameters=plan.normalized_parameters,
                mutation_summary=plan.mutation_summary,
                expires_in=plan.preview_ttl,
                idempotency_key=idempotency_key,
                target_object_id=plan.target_object_id,
                target_revision=plan.target_revision,
                expected_external_effects=plan.expected_external_effects,
                requires_confirmation=plan.requires_confirmation,
                requires_approval=plan.requires_approval,
                canonical_commit_required=plan.canonical_commit_required,
            )
            return await self._respond(
                context=context,
                interaction_id=interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)

    async def confirm(
        self,
        *,
        assertion: ShellAssertion,
        interaction_id: str,
        preview_id: str,
        preview_revision: int,
        expected_revision: int,
        idempotency_key: str,
    ) -> AdapterResponse:
        async def action(context, request_id, trace_id):
            await self._interactions.confirm(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=interaction_id,
                preview_id=preview_id,
                preview_revision=preview_revision,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
            return await self._respond(
                context=context,
                interaction_id=interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)

    async def cancel(
        self,
        *,
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> AdapterResponse:
        async def action(context, request_id, trace_id):
            await self._interactions.cancel(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
            return await self._respond(
                context=context,
                interaction_id=interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)

    async def status(
        self, *, assertion: ShellAssertion, interaction_id: str
    ) -> AdapterResponse:
        async def action(context, request_id, trace_id):
            return await self._respond(
                context=context,
                interaction_id=interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)

    async def view(
        self, *, assertion: ShellAssertion, interaction_id: str
    ) -> AdapterResponse:
        return await self.status(assertion=assertion, interaction_id=interaction_id)

    async def recover(
        self,
        *,
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> AdapterResponse:
        async def action(context, request_id, trace_id):
            await self._interactions.recover(
                workspace=context.workspace,
                actor_id=context.actor_id,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
            return await self._respond(
                context=context,
                interaction_id=interaction_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        return await self._guard(assertion, action)
