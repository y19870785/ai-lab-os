"""Ephemeral receipt issuer for IB-IMP-A; no production signing is performed."""

from __future__ import annotations

import hashlib
import json
import socket

from .protocol import CAPABILITY_FD, FRAME_VERSION, MAX_FRAME_BYTES, _receive_line

_EXPECTED_FIELDS = {
    "frame_version",
    "channel",
    "channel_event_id",
    "event_type",
}


def _receipt(frame: object) -> dict[str, object]:
    if not isinstance(frame, dict) or set(frame) != _EXPECTED_FIELDS:
        return {"accepted": False, "reason": "invalid_frame"}
    event_id = frame.get("channel_event_id")
    if (
        frame.get("frame_version") != FRAME_VERSION
        or frame.get("channel") != "wecom"
        or frame.get("event_type") != "owner_dm_text"
        or not isinstance(event_id, str)
        or not event_id.strip()
    ):
        return {"accepted": False, "reason": "invalid_frame"}
    encoded = event_id.strip().encode("utf-8")
    domain = b"ai-lab/pilot-001/ib-imp-a/receipt/v1\x00"
    digest = hashlib.sha256(domain + len(encoded).to_bytes(4, "big") + encoded).hexdigest()
    return {"accepted": True, "receipt": f"spike:{digest}"}


def serve() -> int:
    sock = socket.socket(fileno=CAPABILITY_FD)
    sock.set_inheritable(False)
    sock.settimeout(10.0)
    try:
        while True:
            try:
                raw = _receive_line(sock)
            except (OSError, RuntimeError):
                return 0
            if len(raw) > MAX_FRAME_BYTES:
                response = {"accepted": False, "reason": "invalid_frame"}
            else:
                try:
                    response = _receipt(json.loads(raw))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response = {"accepted": False, "reason": "invalid_frame"}
            sock.sendall(
                json.dumps(response, sort_keys=True, separators=(",", ":")).encode("ascii")
                + b"\n"
            )
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(serve())
