"""Exact PILOT-001 trusted ingress evidence wire contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrustedIngressEvidenceEnvelopeV1(BaseModel):
    """Adopted V1 envelope; extra authority fields fail validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version: str
    evidence_id: str
    issuer_key_id: str
    channel: str
    channel_account_binding_id: str
    owner_binding_id: str
    conversation_binding_id: str
    received_at: datetime
    event_type: str
    message_content_digest: str
    expires_at: datetime
    signature: str


ENVELOPE_FIELDS = tuple(TrustedIngressEvidenceEnvelopeV1.model_fields)
