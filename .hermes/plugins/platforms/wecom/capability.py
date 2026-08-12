"""Self-contained anonymous capability client for the spike project plugin."""

from __future__ import annotations

import json
import os
import socket
from typing import Any

CAPABILITY_FD = 198
FRAME_VERSION = "pilot-001/ib-imp-a/v1"
MAX_FRAME_BYTES = 16 * 1024


class CapabilityUnavailable(RuntimeError):
    """The supervisor-provided endpoint is missing, closed, or rejects input."""


class CapabilityClient:
    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock

    @classmethod
    def from_inherited_fd(cls) -> CapabilityClient:
        try:
            os.fstat(CAPABILITY_FD)
            os.set_inheritable(CAPABILITY_FD, False)
            sock = socket.socket(fileno=CAPABILITY_FD)
            sock.settimeout(2.0)
        except (OSError, ValueError) as exc:
            raise CapabilityUnavailable("pre-connected capability unavailable") from exc
        return cls(sock)

    def request(self, frame: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(
            frame,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        try:
            self._socket.sendall(encoded + b"\n")
            raw = bytearray()
            while b"\n" not in raw and len(raw) <= MAX_FRAME_BYTES:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise CapabilityUnavailable("capability closed before receipt")
                raw.extend(chunk)
            receipt = json.loads(bytes(raw).split(b"\n", 1)[0])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CapabilityUnavailable("issuer unavailable or invalid receipt") from exc
        if not isinstance(receipt, dict) or receipt.get("accepted") is not True:
            raise CapabilityUnavailable("issuer rejected trusted callback frame")
        return receipt

    def close(self) -> None:
        self._socket.close()
