"""Spike-only anonymous capability framing.

This module is deliberately outside product packages.  It proves transport
isolation only; it is not a TrustedIngressEvidence implementation or signer.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any

CAPABILITY_FD = 198
MAX_FRAME_BYTES = 16 * 1024
FRAME_VERSION = "pilot-001/ib-imp-a/v1"


class CapabilityUnavailable(RuntimeError):
    """The pre-connected anonymous capability is absent or closed."""


def _receive_line(sock: socket.socket) -> bytes:
    data = bytearray()
    while len(data) <= MAX_FRAME_BYTES:
        chunk = sock.recv(4096)
        if not chunk:
            raise CapabilityUnavailable("capability closed before receipt")
        data.extend(chunk)
        newline = data.find(b"\n")
        if newline >= 0:
            return bytes(data[:newline])
    raise CapabilityUnavailable("capability receipt exceeded size limit")


@dataclass(slots=True)
class CapabilityClient:
    """Single pre-connected client; there is no connect or bearer operation."""

    _socket: socket.socket

    @classmethod
    def from_inherited_fd(cls, fd: int = CAPABILITY_FD) -> CapabilityClient:
        try:
            os.fstat(fd)
            os.set_inheritable(fd, False)
            sock = socket.socket(fileno=fd)
            sock.settimeout(2.0)
        except (OSError, ValueError) as exc:
            raise CapabilityUnavailable("pre-connected capability unavailable") from exc
        return cls(sock)

    @classmethod
    def from_socket(cls, sock: socket.socket) -> CapabilityClient:
        """Adopt an already-created test socket on any supported host OS."""

        sock.set_inheritable(False)
        sock.settimeout(2.0)
        return cls(sock)

    def request(self, frame: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(
            frame,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        if len(encoded) > MAX_FRAME_BYTES:
            raise CapabilityUnavailable("capability frame exceeded size limit")
        try:
            self._socket.sendall(encoded + b"\n")
            raw = _receive_line(self._socket)
            receipt = json.loads(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CapabilityUnavailable("issuer unavailable or invalid receipt") from exc
        if not isinstance(receipt, dict) or receipt.get("accepted") is not True:
            raise CapabilityUnavailable("issuer rejected trusted callback frame")
        return receipt

    def close(self) -> None:
        self._socket.close()
