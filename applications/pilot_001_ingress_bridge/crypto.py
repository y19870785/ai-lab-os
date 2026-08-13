"""Pilot-only key separation, stable identity, journal, and Ed25519 JCS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import struct
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from applications.pilot_001_ingress_bridge.models import (
    EVIDENCE_VERSION,
    TrustedIngressEvidenceEnvelopeV1,
    parse_envelope_json,
)

EVENT_TYPE = "owner_dm_text"
CHANNEL = "wecom"
DEFAULT_TTL = timedelta(minutes=5)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    raw = value.removeprefix("ed25519:")
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if _b64(decoded) != raw:
        raise ValueError("noncanonical base64url")
    return decoded


def _lp(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def normalize_message_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n"))


def evidence_id(
    key: bytes,
    *,
    account_binding: str,
    owner_binding: str,
    conversation_binding: str,
    raw_wecom_msgid: str,
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
    material = b"ai-lab/message-content/v1" + _lp(normalize_message_text(text))
    return "hmac-sha256:" + hmac.new(key, material, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class PilotIngressBindings:
    channel_account_binding_id: str
    owner_binding_id: str
    conversation_binding_id: str

    def tuple(self) -> tuple[str, str, str]:
        return (
            self.channel_account_binding_id,
            self.owner_binding_id,
            self.conversation_binding_id,
        )


def _load_bindings(root: Path) -> tuple[PilotIngressBindings, str]:
    values = json.loads((root / "bindings.json").read_text(encoding="utf-8"))
    trusted_issuer_key_id = values.pop("trusted_issuer_key_id")
    return PilotIngressBindings(**values), trusted_issuer_key_id


class PilotIngressVerifierKeys:
    """Verification-only key material; deliberately cannot issue evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.public_key = Ed25519PublicKey.from_public_bytes(
            (root / "signing_public.key").read_bytes()
        )
        self.content_binding_key = (root / "content_binding.key").read_bytes()
        self.bindings, configured_issuer_key_id = _load_bindings(root)
        public = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.trusted_issuer_key_id = "tik_" + hashlib.sha256(public).hexdigest()[:24]
        if configured_issuer_key_id != self.trusted_issuer_key_id:
            raise RuntimeError("Pilot ingress verifier config does not match public key")

    def verify(self, envelope: TrustedIngressEvidenceEnvelopeV1) -> None:
        if envelope.issuer_key_id != self.trusted_issuer_key_id:
            raise ValueError("trusted ingress issuer is not trusted")
        unsigned = envelope.model_dump(mode="json", exclude={"signature"})
        self.public_key.verify(_unb64(envelope.signature), rfc8785.dumps(unsigned))


class PilotIngressIssuerKeys:
    """Issuer-only signing/identity authority with durable issuance journal."""

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
        self.bindings, configured_issuer_key_id = _load_bindings(root)
        public = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.issuer_key_id = "tik_" + hashlib.sha256(public).hexdigest()[:24]
        if configured_issuer_key_id != self.issuer_key_id:
            raise RuntimeError("Pilot ingress issuer config does not match public key")
        self._journal_path = root / "issuance.sqlite3"
        self._initialize_journal()

    @classmethod
    def bootstrap(cls, data_dir: Path) -> PilotIngressIssuerKeys:
        root = data_dir / "pilot-001" / "trusted-ingress"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        paths = {
            "private": root / "signing_private.key",
            "public": root / "signing_public.key",
            "identity": root / "event_identity.key",
            "content": root / "content_binding.key",
            "bindings": root / "bindings.json",
        }
        binary_names = {"private", "public", "identity", "content"}
        existing_binary = {name for name in binary_names if paths[name].exists()}
        if existing_binary and existing_binary != binary_names:
            raise RuntimeError("partial Pilot ingress key set; refusing replacement")
        if not existing_binary and paths["bindings"].exists():
            raise RuntimeError("binding config exists without Pilot ingress keys")
        if not existing_binary:
            private = Ed25519PrivateKey.generate()
            binary = {
                "private": private.private_bytes(
                    serialization.Encoding.Raw,
                    serialization.PrivateFormat.Raw,
                    serialization.NoEncryption(),
                ),
                "public": private.public_key().public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                ),
                "identity": secrets.token_bytes(32),
                "content": secrets.token_bytes(32),
            }
            for name, value in binary.items():
                fd = os.open(paths[name], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(value)
        if not paths["bindings"].exists():
            public = Ed25519PublicKey.from_public_bytes(paths["public"].read_bytes())
            public_bytes = public.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            bindings = {
                "channel_account_binding_id": "acct_" + secrets.token_urlsafe(24),
                "owner_binding_id": "owner_" + secrets.token_urlsafe(24),
                "conversation_binding_id": "conv_" + secrets.token_urlsafe(24),
                "trusted_issuer_key_id": (
                    "tik_" + hashlib.sha256(public_bytes).hexdigest()[:24]
                ),
            }
            fd = os.open(
                paths["bindings"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(bindings, handle, sort_keys=True, separators=(",", ":"))
        for path in paths.values():
            try:
                path.chmod(0o600)
            except OSError:
                pass
        return cls(root)

    def _initialize_journal(self) -> None:
        with sqlite3.connect(self._journal_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS issued_evidence (
                evidence_id TEXT PRIMARY KEY,
                envelope TEXT NOT NULL,
                first_received_at TEXT NOT NULL,
                first_expires_at TEXT NOT NULL,
                payload_identity TEXT NOT NULL
                )"""
            )
        try:
            self._journal_path.chmod(0o600)
        except OSError:
            pass

    def issue(
        self,
        *,
        raw_wecom_msgid: str,
        text: str,
        bindings: PilotIngressBindings | None = None,
        received_at: datetime | None = None,
    ) -> TrustedIngressEvidenceEnvelopeV1:
        if not isinstance(raw_wecom_msgid, str) or not raw_wecom_msgid.strip():
            raise ValueError("trusted_ingress.channel_event_id_unavailable")
        selected = bindings or self.bindings
        identifier = evidence_id(
            self.event_identity_key,
            account_binding=selected.channel_account_binding_id,
            owner_binding=selected.owner_binding_id,
            conversation_binding=selected.conversation_binding_id,
            raw_wecom_msgid=raw_wecom_msgid,
        )
        digest = content_digest(self.content_binding_key, text)
        payload_identity = hashlib.sha256(
            rfc8785.dumps(
                {
                    "channel": CHANNEL,
                    "bindings": selected.tuple(),
                    "event_type": EVENT_TYPE,
                    "message_content_digest": digest,
                }
            )
        ).hexdigest()
        with sqlite3.connect(self._journal_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT envelope,payload_identity FROM issued_evidence WHERE evidence_id=?",
                (identifier,),
            ).fetchone()
            if row is not None:
                if row["payload_identity"] != payload_identity:
                    raise ValueError("trusted ingress issuance identity conflict")
                return parse_envelope_json(row["envelope"])
            now = (received_at or datetime.now(UTC)).astimezone(UTC)
            unsigned = {
                "evidence_version": EVIDENCE_VERSION,
                "evidence_id": identifier,
                "issuer_key_id": self.issuer_key_id,
                "channel": CHANNEL,
                "channel_account_binding_id": selected.channel_account_binding_id,
                "owner_binding_id": selected.owner_binding_id,
                "conversation_binding_id": selected.conversation_binding_id,
                "received_at": _timestamp(now),
                "event_type": EVENT_TYPE,
                "message_content_digest": digest,
                "expires_at": _timestamp(now + DEFAULT_TTL),
            }
            signature = "ed25519:" + _b64(
                self.private_key.sign(rfc8785.dumps(unsigned))
            )
            envelope = TrustedIngressEvidenceEnvelopeV1(
                **unsigned, signature=signature
            )
            wire = envelope.model_dump_json()
            connection.execute(
                """INSERT INTO issued_evidence
                (evidence_id,envelope,first_received_at,first_expires_at,payload_identity)
                VALUES(?,?,?,?,?)""",
                (
                    identifier,
                    wire,
                    envelope.received_at,
                    envelope.expires_at,
                    payload_identity,
                ),
            )
            return envelope
