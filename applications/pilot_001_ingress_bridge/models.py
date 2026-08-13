"""Exact PILOT-001 trusted ingress evidence wire contract."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

EVIDENCE_VERSION = "trusted-ingress-evidence/v1"
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_BINDINGS = {
    "channel_account_binding_id": re.compile(r"^acct_[A-Za-z0-9_-]+$"),
    "owner_binding_id": re.compile(r"^owner_[A-Za-z0-9_-]+$"),
    "conversation_binding_id": re.compile(r"^conv_[A-Za-z0-9_-]+$"),
}
_DIGEST = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_SIGNATURE = re.compile(r"^ed25519:[A-Za-z0-9_-]{86}$")
_EVIDENCE_ID = re.compile(r"^tie_[a-z2-7]{52}$")
_ISSUER_KEY_ID = re.compile(r"^tik_[0-9a-f]{24}$")


class TrustedIngressEvidenceEnvelopeV1(BaseModel):
    """Adopted V1 envelope preserving canonical wire strings for verification."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evidence_version: str
    evidence_id: str
    issuer_key_id: str
    channel: str
    channel_account_binding_id: str
    owner_binding_id: str
    conversation_binding_id: str
    received_at: str
    event_type: str
    message_content_digest: str
    expires_at: str
    signature: str

    @field_validator("evidence_version")
    @classmethod
    def _exact_version(cls, value: str) -> str:
        if value != EVIDENCE_VERSION:
            raise ValueError("wrong evidence_version")
        return value

    @field_validator("channel")
    @classmethod
    def _exact_channel(cls, value: str) -> str:
        if value != "wecom":
            raise ValueError("wrong channel")
        return value

    @field_validator("event_type")
    @classmethod
    def _exact_event_type(cls, value: str) -> str:
        if value != "owner_dm_text":
            raise ValueError("wrong event_type")
        return value

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, value: str) -> str:
        if not _EVIDENCE_ID.fullmatch(value):
            raise ValueError("invalid evidence_id")
        return value

    @field_validator("issuer_key_id")
    @classmethod
    def _issuer_key_id_format(cls, value: str) -> str:
        if not _ISSUER_KEY_ID.fullmatch(value):
            raise ValueError("invalid issuer_key_id")
        return value

    @field_validator("received_at", "expires_at")
    @classmethod
    def _canonical_timestamp(cls, value: str) -> str:
        if not _TIMESTAMP.fullmatch(value):
            raise ValueError("timestamp must be UTC RFC3339 milliseconds with Z")
        return value

    @field_validator(*tuple(_BINDINGS))
    @classmethod
    def _opaque_binding(cls, value: str, info: Any) -> str:
        if not _BINDINGS[info.field_name].fullmatch(value):
            raise ValueError("binding ID is not operator-provisioned opaque V1 form")
        return value

    @field_validator("message_content_digest")
    @classmethod
    def _digest_format(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("invalid message_content_digest")
        return value

    @field_validator("signature")
    @classmethod
    def _signature_format(cls, value: str) -> str:
        if not _SIGNATURE.fullmatch(value):
            raise ValueError("invalid Ed25519 signature encoding")
        return value


ENVELOPE_FIELDS = tuple(TrustedIngressEvidenceEnvelopeV1.model_fields)


def parse_envelope_json(payload: str) -> TrustedIngressEvidenceEnvelopeV1:
    """Reject duplicate keys before exact Pydantic field/value validation."""

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    decoded = json.loads(payload, object_pairs_hook=pairs)
    if not isinstance(decoded, dict):
        raise TypeError("evidence envelope must be a JSON object")
    return TrustedIngressEvidenceEnvelopeV1.model_validate(decoded)
