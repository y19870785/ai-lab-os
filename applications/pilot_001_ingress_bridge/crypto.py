"""Pilot-only key bootstrap, stable identity, content binding, and Ed25519 JCS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from applications.pilot_001_ingress_bridge.models import (
    TrustedIngressEvidenceEnvelopeV1,
)

EVIDENCE_VERSION = "1"
EVENT_TYPE = "owner_dm_text"
CHANNEL = "wecom"
DEFAULT_TTL = timedelta(minutes=5)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _lp(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def normalize_message_text(value: str) -> str:
    """Apply the adopted content normalization and nothing semantic."""

    return unicodedata.normalize("NFC", value.replace("\r\n", "\n"))


def _binding(key: bytes, kind: str, raw_value: str) -> str:
    material = b"ai-lab/trusted-ingress-binding/v1" + _lp(kind) + _lp(raw_value)
    return "tib_" + _b64(hmac.new(key, material, hashlib.sha256).digest())


def evidence_id(
    key: bytes, *, account_binding: str, owner_binding: str,
    conversation_binding: str, raw_wecom_msgid: str,
) -> str:
    material = (
        b"ai-lab/trusted-ingress-event/v1"
        + _lp(CHANNEL)
        + _lp(account_binding)
        + _lp(owner_binding)
        + _lp(conversation_binding)
        + _lp(raw_wecom_msgid)
    )
    digest = hmac.new(key, material, hashlib.sha256).digest()
    return "tie_" + base64.b32encode(digest).rstrip(b"=").decode("ascii").lower()


def content_digest(key: bytes, text: str) -> str:
    normalized = normalize_message_text(text)
    material = b"ai-lab/message-content/v1" + _lp(normalized)
    return "tmc_" + _b64(hmac.new(key, material, hashlib.sha256).digest())


class PilotIngressKeys:
    """In-memory Pilot keys loaded from the operator-owned data directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.private_key = Ed25519PrivateKey.from_private_bytes(
            (root / "signing_private.key").read_bytes()
        )
        self.public_key = Ed25519PublicKey.from_public_bytes(
            (root / "signing_public.key").read_bytes()
        )
        self.event_identity_key = (root / "event_identity.key").read_bytes()
        self.content_binding_key = (root / "content_binding.key").read_bytes()
        public = self.public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.issuer_key_id = "tik_" + hashlib.sha256(public).hexdigest()[:24]

    @classmethod
    def bootstrap(cls, data_dir: Path) -> PilotIngressKeys:
        root = data_dir / "pilot-001" / "trusted-ingress"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        paths = {
            "private": root / "signing_private.key",
            "public": root / "signing_public.key",
            "identity": root / "event_identity.key",
            "content": root / "content_binding.key",
        }
        existing = {name for name, path in paths.items() if path.exists()}
        if existing and len(existing) != len(paths):
            raise RuntimeError("partial Pilot ingress key set; refusing replacement")
        if not existing:
            private = Ed25519PrivateKey.generate()
            values = {
                "private": private.private_bytes(
                    serialization.Encoding.Raw,
                    serialization.PrivateFormat.Raw,
                    serialization.NoEncryption(),
                ),
                "public": private.public_key().public_bytes(
                    serialization.Encoding.Raw,
                    serialization.PublicFormat.Raw,
                ),
                "identity": secrets.token_bytes(32),
                "content": secrets.token_bytes(32),
            }
            for name, value in values.items():
                fd = os.open(paths[name], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(value)
        for path in paths.values():
            try:
                path.chmod(0o600)
            except OSError:
                pass
        return cls(root)

    def issue(
        self, *, raw_account_id: str, raw_owner_id: str,
        raw_conversation_id: str, raw_wecom_msgid: str, text: str,
        received_at: datetime | None = None, ttl: timedelta = DEFAULT_TTL,
    ) -> TrustedIngressEvidenceEnvelopeV1:
        if not isinstance(raw_wecom_msgid, str) or not raw_wecom_msgid.strip():
            raise ValueError("trusted_ingress.channel_event_id_unavailable")
        now = (received_at or datetime.now(UTC)).astimezone(UTC)
        account = _binding(self.event_identity_key, "account", raw_account_id)
        owner = _binding(self.event_identity_key, "owner", raw_owner_id)
        conversation = _binding(
            self.event_identity_key, "conversation", raw_conversation_id
        )
        unsigned = {
            "evidence_version": EVIDENCE_VERSION,
            "evidence_id": evidence_id(
                self.event_identity_key,
                account_binding=account,
                owner_binding=owner,
                conversation_binding=conversation,
                raw_wecom_msgid=raw_wecom_msgid,
            ),
            "issuer_key_id": self.issuer_key_id,
            "channel": CHANNEL,
            "channel_account_binding_id": account,
            "owner_binding_id": owner,
            "conversation_binding_id": conversation,
            "received_at": now.isoformat().replace("+00:00", "Z"),
            "event_type": EVENT_TYPE,
            "message_content_digest": content_digest(self.content_binding_key, text),
            "expires_at": (now + ttl).isoformat().replace("+00:00", "Z"),
        }
        signature = _b64(self.private_key.sign(rfc8785.dumps(unsigned)))
        return TrustedIngressEvidenceEnvelopeV1(**unsigned, signature=signature)

    def verify(self, envelope: TrustedIngressEvidenceEnvelopeV1) -> None:
        if envelope.issuer_key_id != self.issuer_key_id:
            raise ValueError("trusted ingress issuer is not trusted")
        unsigned = envelope.model_dump(mode="json", exclude={"signature"})
        self.public_key.verify(_unb64(envelope.signature), rfc8785.dumps(unsigned))

    def expected_bindings(
        self, *, raw_account_id: str, raw_owner_id: str, raw_conversation_id: str,
    ) -> tuple[str, str, str]:
        return (
            _binding(self.event_identity_key, "account", raw_account_id),
            _binding(self.event_identity_key, "owner", raw_owner_id),
            _binding(self.event_identity_key, "conversation", raw_conversation_id),
        )
