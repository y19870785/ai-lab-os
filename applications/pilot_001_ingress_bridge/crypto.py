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


def _load_bindings(root: Path) -> PilotIngressBindings:
    values = json.loads((root / "bindings.json").read_text(encoding="utf-8"))
    values.pop("trusted_issuer_key_id", None)
    return PilotIngressBindings(**values)


def _write_private(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(value)


def _replace_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _key_id(public_bytes: bytes) -> str:
    return "tik_" + hashlib.sha256(public_bytes).hexdigest()[:24]


class PilotIngressVerifierKeys:
    """Verification-only key material; deliberately cannot issue evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._load_projection()

    def _load_projection(self) -> None:
        allowed = {
            "bindings.json",
            "content_binding.key",
            "public_keys",
            "trusted_issuers.json",
        }
        unexpected = {path.name for path in self.root.iterdir()} - allowed
        if unexpected:
            raise RuntimeError("verifier projection contains non-verifier material")
        self.content_binding_key = (self.root / "content_binding.key").read_bytes()
        self.bindings = _load_bindings(self.root)
        config = json.loads(
            (self.root / "trusted_issuers.json").read_text(encoding="utf-8")
        )
        self.active_issuer_key_id = str(config["active_issuer_key_id"])
        trusted_ids = tuple(str(value) for value in config["trusted_issuer_key_ids"])
        if self.active_issuer_key_id not in trusted_ids or len(set(trusted_ids)) != len(
            trusted_ids
        ):
            raise RuntimeError("invalid trusted issuer configuration")
        self.public_keys: dict[str, Ed25519PublicKey] = {}
        for issuer_key_id in trusted_ids:
            public_bytes = (
                self.root / "public_keys" / f"{issuer_key_id}.key"
            ).read_bytes()
            if _key_id(public_bytes) != issuer_key_id:
                raise RuntimeError("trusted issuer public key does not match key ID")
            self.public_keys[issuer_key_id] = Ed25519PublicKey.from_public_bytes(
                public_bytes
            )

    def verify(self, envelope: TrustedIngressEvidenceEnvelopeV1) -> None:
        public_key = self.public_keys.get(envelope.issuer_key_id)
        if public_key is None:
            self._load_projection()
            public_key = self.public_keys.get(envelope.issuer_key_id)
        if public_key is None:
            raise ValueError("trusted ingress issuer is not trusted")
        unsigned = envelope.model_dump(mode="json", exclude={"signature"})
        public_key.verify(_unb64(envelope.signature), rfc8785.dumps(unsigned))


class PilotIngressIssuerKeys:
    """Issuer-only signing/identity authority with durable issuance journal."""

    def __init__(self, root: Path) -> None:
        self.root = root
        active = json.loads(
            (root / "active_signing_key.json").read_text(encoding="utf-8")
        )
        self.issuer_key_id = str(active["active_issuer_key_id"])
        key_root = root / "signing_keys"
        self.private_key = Ed25519PrivateKey.from_private_bytes(
            (key_root / f"{self.issuer_key_id}.private").read_bytes()
        )
        self.public_key = Ed25519PublicKey.from_public_bytes(
            (key_root / f"{self.issuer_key_id}.public").read_bytes()
        )
        self.event_identity_key = (root / "event_identity.key").read_bytes()
        self.content_binding_key = (root / "content_binding.key").read_bytes()
        self.bindings = _load_bindings(root)
        public = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        if _key_id(public) != self.issuer_key_id:
            raise RuntimeError("Pilot ingress active signing key is inconsistent")
        self._journal_path = root / "issuance.sqlite3"
        self._initialize_journal()

    @classmethod
    def bootstrap(
        cls, *, issuer_root: Path, verifier_root: Path
    ) -> PilotIngressIssuerKeys:
        issuer_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        signing_keys = issuer_root / "signing_keys"
        signing_keys.mkdir(mode=0o700, exist_ok=True)
        paths = {
            "identity": issuer_root / "event_identity.key",
            "content": issuer_root / "content_binding.key",
            "bindings": issuer_root / "bindings.json",
            "active": issuer_root / "active_signing_key.json",
        }
        identity_content = {name for name in ("identity", "content") if paths[name].exists()}
        if identity_content and identity_content != {"identity", "content"}:
            raise RuntimeError("partial Pilot ingress identity key set")
        if not identity_content:
            _write_private(paths["identity"], secrets.token_bytes(32))
            _write_private(paths["content"], secrets.token_bytes(32))
        if not paths["active"].exists():
            legacy_private = issuer_root / "signing_private.key"
            legacy_public = issuer_root / "signing_public.key"
            if legacy_private.exists() != legacy_public.exists():
                raise RuntimeError("partial legacy signing key set")
            if legacy_private.exists():
                private_bytes = legacy_private.read_bytes()
                public_bytes = legacy_public.read_bytes()
            else:
                private = Ed25519PrivateKey.generate()
                private_bytes = private.private_bytes(
                    serialization.Encoding.Raw,
                    serialization.PrivateFormat.Raw,
                    serialization.NoEncryption(),
                )
                public_bytes = private.public_key().public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                )
            issuer_key_id = _key_id(public_bytes)
            private_path = signing_keys / f"{issuer_key_id}.private"
            public_path = signing_keys / f"{issuer_key_id}.public"
            if not private_path.exists():
                _write_private(private_path, private_bytes)
            if not public_path.exists():
                _write_private(public_path, public_bytes)
            _replace_json(paths["active"], {"active_issuer_key_id": issuer_key_id})
        if not paths["bindings"].exists():
            bindings = {
                "channel_account_binding_id": "acct_" + secrets.token_urlsafe(24),
                "owner_binding_id": "owner_" + secrets.token_urlsafe(24),
                "conversation_binding_id": "conv_" + secrets.token_urlsafe(24),
            }
            _replace_json(paths["bindings"], bindings)
        issuer = cls(issuer_root)
        issuer.project_verifier_material(verifier_root)
        for path in (
            paths["identity"],
            paths["content"],
            paths["bindings"],
            paths["active"],
            *signing_keys.iterdir(),
        ):
            try:
                path.chmod(0o600)
            except OSError:
                pass
        return issuer

    def project_verifier_material(self, verifier_root: Path) -> None:
        """Create/update the verifier-only deployment projection."""

        verifier_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        allowed = {
            "bindings.json",
            "content_binding.key",
            "public_keys",
            "trusted_issuers.json",
        }
        unexpected = {path.name for path in verifier_root.iterdir()} - allowed
        if unexpected:
            raise RuntimeError("verifier projection contains non-verifier material")
        content_path = verifier_root / "content_binding.key"
        if content_path.exists():
            if content_path.read_bytes() != self.content_binding_key:
                raise RuntimeError("verifier content binding key conflicts with issuer")
        else:
            _write_private(content_path, self.content_binding_key)
        binding_path = verifier_root / "bindings.json"
        binding_value = {
            "channel_account_binding_id": self.bindings.channel_account_binding_id,
            "owner_binding_id": self.bindings.owner_binding_id,
            "conversation_binding_id": self.bindings.conversation_binding_id,
        }
        if binding_path.exists():
            if _load_bindings(verifier_root) != self.bindings:
                raise RuntimeError("verifier opaque bindings conflict with issuer")
        else:
            _replace_json(binding_path, binding_value)
        public_root = verifier_root / "public_keys"
        public_root.mkdir(mode=0o700, exist_ok=True)
        public_bytes = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        public_path = public_root / f"{self.issuer_key_id}.key"
        if public_path.exists():
            if public_path.read_bytes() != public_bytes:
                raise RuntimeError("verifier public key conflicts with issuer key ID")
        else:
            _write_private(public_path, public_bytes)
        config_path = verifier_root / "trusted_issuers.json"
        trusted_ids: list[str] = []
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            trusted_ids = [str(value) for value in config["trusted_issuer_key_ids"]]
        if self.issuer_key_id not in trusted_ids:
            trusted_ids.append(self.issuer_key_id)
        _replace_json(
            config_path,
            {
                "active_issuer_key_id": self.issuer_key_id,
                "trusted_issuer_key_ids": sorted(set(trusted_ids)),
            },
        )
        for path in (content_path, binding_path, config_path, *public_root.iterdir()):
            try:
                path.chmod(0o600)
            except OSError:
                pass

    def rotate_signing_key(self, verifier_root: Path) -> PilotIngressIssuerKeys:
        """Rotate only signing authority; preserve identity, binding, and journal."""

        private = Ed25519PrivateKey.generate()
        private_bytes = private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        public_bytes = private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        issuer_key_id = _key_id(public_bytes)
        signing_keys = self.root / "signing_keys"
        _write_private(signing_keys / f"{issuer_key_id}.private", private_bytes)
        _write_private(signing_keys / f"{issuer_key_id}.public", public_bytes)
        _replace_json(
            self.root / "active_signing_key.json",
            {"active_issuer_key_id": issuer_key_id},
        )
        rotated = type(self)(self.root)
        rotated.project_verifier_material(verifier_root)
        return rotated

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
