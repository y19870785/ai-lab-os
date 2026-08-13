"""Pilot-only Preview challenge and trusted evidence confirmation service."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from applications.pilot_001_ingress_bridge.crypto import (
    CHANNEL,
    EVENT_TYPE,
    PilotIngressVerifierKeys,
    content_digest,
    parse_timestamp,
)
from applications.pilot_001_ingress_bridge.models import parse_envelope_json
from applications.trusted_interaction_adapter.models import ShellAssertion
from applications.trusted_interaction_adapter.pilot_001 import ALLOWED_OPERATION
from applications.trusted_interaction_adapter.service import TrustedInteractionAdapter
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.interaction import InteractionService, LifecycleState


@dataclass(frozen=True, repr=False)
class PilotIngressAuthority:
    raw_account_id: str
    raw_owner_id: str
    raw_conversation_id: str


class Pilot001IngressConfirmationService:
    """Narrow internal-pilot authority; deliberately stops at AUTHORIZED."""

    def __init__(
        self, *, adapter: TrustedInteractionAdapter,
        interactions: InteractionService, keys: PilotIngressVerifierKeys,
        authority: PilotIngressAuthority,
    ) -> None:
        self._adapter = adapter
        self._interactions = interactions
        self._repository = interactions._repository
        self._keys = keys
        self._authority = authority

    @staticmethod
    def _failure(code: str, message: str, operation: str) -> FailureException:
        return FailureException(
            FailureInfo(
                code=code,
                category=ErrorCategory.PERMISSION_DENIED,
                message=message,
                component="pilot_001_ingress_confirmation",
                operation=operation,
                retryable=False,
            )
        )

    def assertion(self, *, message_id: str = "trusted-ingress") -> ShellAssertion:
        return ShellAssertion(
            channel=CHANNEL,
            shell="hermes",
            shell_session_id="pilot-001-internal",
            channel_identity=self._authority.raw_owner_id,
            message_id=message_id,
            correlation={"request_id": message_id, "trace_id": message_id},
        )

    async def accept_evidence(
        self, envelope_wire: str,
    ) -> str:
        try:
            envelope = parse_envelope_json(envelope_wire)
            self._keys.verify(envelope)
        except Exception as exc:
            raise self._failure(
                "trusted_ingress.signature_invalid",
                "Trusted ingress signature validation failed",
                "accept_evidence",
            ) from exc
        expected = self._keys.bindings.tuple()
        actual = (
            envelope.channel_account_binding_id,
            envelope.owner_binding_id,
            envelope.conversation_binding_id,
        )
        if envelope.channel != CHANNEL or envelope.event_type != EVENT_TYPE or actual != expected:
            raise self._failure(
                "trusted_ingress.binding_denied",
                "Trusted ingress channel or configured binding does not match",
                "accept_evidence",
            )
        payload = envelope_wire
        await self._repository.store_trusted_ingress_evidence(
            evidence_id=envelope.evidence_id,
            payload=payload,
            payload_digest=hashlib.sha256(payload.encode()).hexdigest(),
            accepted_at=datetime.now(UTC).isoformat(),
            verification_key_id=envelope.issuer_key_id,
        )
        return envelope.evidence_id

    async def preview(
        self, *, parameters: dict[str, object], idempotency_key: str,
    ) -> dict[str, object]:
        response = await self._adapter.preview(
            assertion=self.assertion(message_id=idempotency_key),
            requested_operation=ALLOWED_OPERATION,
            parameters=parameters,
            idempotency_key=idempotency_key,
        )
        wire = response.model_dump(mode="json")
        if response.failure is not None or response.preview is None:
            return wire
        status = await self._interactions.status(
            workspace=(await self._adapter._resolve(self.assertion())).workspace,
            actor_id=(await self._adapter._resolve(self.assertion())).actor_id,
            interaction_id=response.interaction_id,
        )
        preview = status.preview
        assert preview is not None
        challenge = "-".join(
            [secrets.token_hex(2).upper(), secrets.token_hex(2).upper()]
        )
        created_at = datetime.now(UTC)
        if created_at <= preview.created_at:
            created_at = preview.created_at + timedelta(microseconds=1)
        expected_text = f"确认 {challenge}"
        await self._repository.store_confirmation_challenge(
            challenge_id="pch_" + secrets.token_hex(16),
            interaction_id=response.interaction_id,
            preview_id=preview.preview_id,
            preview_revision=preview.preview_revision,
            interaction_revision=response.revision,
            challenge_digest=hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
            created_at=created_at.isoformat(),
            expires_at=min(preview.expires_at, created_at + timedelta(minutes=5)).isoformat(),
        )
        wire["preview_confirmation_challenge"] = challenge
        wire["confirmation_instruction"] = expected_text
        return wire

    async def confirm(
        self, *, interaction_id: str, expected_revision: int,
        evidence_id: str, confirmation_text: str, idempotency_key: str,
    ) -> dict[str, object]:
        context = await self._adapter._resolve(self.assertion(message_id=evidence_id))
        status = await self._interactions.status(
            workspace=context.workspace,
            actor_id=context.actor_id,
            interaction_id=interaction_id,
        )
        preview = status.preview
        if (
            preview is None
            or status.interaction.lifecycle_state != LifecycleState.AWAITING_CONFIRMATION
            or status.interaction.revision != expected_revision
        ):
            raise self._failure(
                "trusted_confirmation.revision_denied",
                "Interaction or Preview revision is not confirmable",
                "confirm",
            )
        record = await self._repository.trusted_ingress_evidence(evidence_id)
        challenge = await self._repository.confirmation_challenge(
            interaction_id, preview.preview_id
        )
        if record is None or challenge is None:
            raise self._failure(
                "trusted_confirmation.evidence_missing",
                "Fresh trusted ingress evidence and challenge are required",
                "confirm",
            )
        try:
            envelope = parse_envelope_json(str(record["payload"]))
            self._keys.verify(envelope)
        except Exception as exc:
            raise self._failure(
                "trusted_confirmation.signature_invalid",
                "Evidence signature is invalid",
                "confirm",
            ) from exc
        now = datetime.now(UTC)
        received_at = parse_timestamp(envelope.received_at)
        accepted_at = datetime.fromisoformat(str(record["accepted_at"])).astimezone(UTC)
        challenge_created = datetime.fromisoformat(str(challenge["created_at"])).astimezone(UTC)
        challenge_expires = datetime.fromisoformat(str(challenge["expires_at"])).astimezone(UTC)
        expected_bindings = self._keys.bindings.tuple()
        actual_bindings = (
            envelope.channel_account_binding_id,
            envelope.owner_binding_id,
            envelope.conversation_binding_id,
        )
        checks = (
            record["verification_status"] == "VERIFIED",
            record["consumption_status"] == "UNUSED",
            challenge["status"] == "ACTIVE",
            envelope.channel == CHANNEL,
            envelope.event_type == EVENT_TYPE,
            actual_bindings == expected_bindings,
            received_at > preview.created_at,
            accepted_at > preview.created_at,
            challenge_created > preview.created_at,
            now < parse_timestamp(envelope.expires_at),
            now < challenge_expires,
            int(challenge["preview_revision"]) == preview.preview_revision,
            int(challenge["interaction_revision"]) == expected_revision,
            hashlib.sha256(confirmation_text.encode("utf-8")).hexdigest()
            == challenge["challenge_digest"],
            content_digest(self._keys.content_binding_key, confirmation_text)
            == envelope.message_content_digest,
        )
        if not all(checks):
            raise self._failure(
                "trusted_confirmation.validation_denied",
                "Trusted evidence, ordering, challenge, content, or revision is invalid",
                "confirm",
            )
        confirmation = await self._interactions.confirm(
            workspace=context.workspace,
            actor_id=context.actor_id,
            interaction_id=interaction_id,
            preview_id=preview.preview_id,
            preview_revision=preview.preview_revision,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            trusted_evidence_consumption={
                "evidence_id": evidence_id,
                "evidence_revision": int(record["revision"]),
                "challenge_id": challenge["challenge_id"],
                "preview_id": preview.preview_id,
                "preview_revision": preview.preview_revision,
                "consumed_at": now.isoformat(),
            },
        )
        final = await self._adapter.status(
            assertion=self.assertion(message_id=evidence_id),
            interaction_id=interaction_id,
        )
        wire = final.model_dump(mode="json")
        wire["confirmation_id"] = confirmation.confirmation_id
        return wire
