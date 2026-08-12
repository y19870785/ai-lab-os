"""Same-user and child-process attack probes for the capability spike."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import platform
import socket
import sys

from .protocol import CAPABILITY_FD, FRAME_VERSION, CapabilityClient


def fd_visible() -> bool:
    try:
        os.fstat(CAPABILITY_FD)
    except OSError:
        return False
    return True


def _pidfd_getfd(target_pid: int) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        return {"supported": False, "duplicated": False, "errno": None}
    libc = ctypes.CDLL(None, use_errno=True)
    pidfd = libc.syscall(434, target_pid, 0)
    if pidfd < 0:
        return {
            "supported": True,
            "duplicated": False,
            "errno": ctypes.get_errno(),
        }
    try:
        duplicate = libc.syscall(438, pidfd, CAPABILITY_FD, 0)
        if duplicate >= 0:
            invoked = False
            try:
                client = CapabilityClient.from_socket(socket.socket(fileno=duplicate))
                receipt = client.request(
                    {
                        "frame_version": FRAME_VERSION,
                        "channel": "wecom",
                        "channel_event_id": "same-user-forged-event",
                        "event_type": "owner_dm_text",
                    }
                )
                invoked = receipt.get("accepted") is True
                client.close()
            except (OSError, RuntimeError):
                os.close(duplicate)
            return {
                "supported": True,
                "duplicated": True,
                "invoked": invoked,
                "errno": None,
            }
        return {
            "supported": True,
            "duplicated": False,
            "invoked": False,
            "errno": ctypes.get_errno(),
        }
    finally:
        os.close(pidfd)


def attack_process(target_pid: int) -> dict[str, object]:
    proc_path = f"/proc/{target_pid}/fd/{CAPABILITY_FD}"
    proc_duplicated = False
    proc_errno: int | None = None
    try:
        duplicate = os.open(proc_path, os.O_RDWR)
    except OSError as exc:
        proc_errno = exc.errno
    else:
        proc_duplicated = True
        os.close(duplicate)
    return {
        "fd_in_environment": any(
            key.upper()
            in {
                "CAPABILITY_FD",
                "ISSUER_CAPABILITY",
                "ISSUER_FD",
                "SIGNER_TOKEN",
            }
            for key in os.environ
        ),
        "fd_in_argv": str(CAPABILITY_FD) in sys.argv,
        "proc_duplicated": proc_duplicated,
        "proc_errno": proc_errno,
        "pidfd_getfd": _pidfd_getfd(target_pid),
        "denied_errno": errno.EPERM,
    }


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({"fd_visible": fd_visible()}, sort_keys=True))
        return 0
    if len(sys.argv) == 2:
        print(json.dumps(attack_process(int(sys.argv[1])), sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
