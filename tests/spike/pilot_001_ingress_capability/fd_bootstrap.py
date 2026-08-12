"""Trusted exec bootstrap that maps the sole inherited socket to FD 198."""

from __future__ import annotations

import os
import socket
import sys

from .protocol import CAPABILITY_FD


def _find_inherited_socket() -> int:
    candidates: list[int] = []
    soft_limit = min(1024, os.sysconf("SC_OPEN_MAX"))
    for fd in range(3, soft_limit):
        if fd == CAPABILITY_FD:
            continue
        try:
            probe = socket.socket(fileno=fd)
        except OSError:
            continue
        else:
            probe.detach()
            candidates.append(fd)
    if len(candidates) != 1:
        raise RuntimeError("expected exactly one inherited anonymous socket")
    return candidates[0]


def main() -> int:
    if os.name != "posix" or len(sys.argv) < 3 or sys.argv[1] != "--":
        return 2
    source_fd = _find_inherited_socket()
    os.dup2(source_fd, CAPABILITY_FD, inheritable=True)
    if source_fd != CAPABILITY_FD:
        os.close(source_fd)
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
