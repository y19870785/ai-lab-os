"""Deterministic POSIX launch pattern for the IB-IMP-A capability spike."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass


def spawn_with_capability(
    argv: Sequence[str],
    endpoint: socket.socket,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
) -> subprocess.Popen[bytes]:
    """Spawn one process with exactly one anonymous endpoint.

    The endpoint is inherited as a fixed descriptor so no secret, path, token,
    or descriptor number is added to argv/environment.  The child adopts it
    and immediately applies close-on-exec before any Agent/tool child exists.
    """

    if os.name != "posix":
        raise RuntimeError("IB-IMP-A supervisor requires the real POSIX/WSL2 deployment")
    source_fd = endpoint.fileno()
    bootstrap = [
        sys.executable,
        "-m",
        "tests.spike.pilot_001_ingress_capability.fd_bootstrap",
        "--",
        *argv,
    ]
    return subprocess.Popen(
        bootstrap,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        close_fds=True,
        pass_fds=(source_fd,),
    )


@dataclass(slots=True)
class SupervisedPair:
    issuer: subprocess.Popen[bytes]
    gateway: subprocess.Popen[bytes]

    def stop(self) -> None:
        for process in (self.gateway, self.issuer):
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 3.0
        for process in (self.gateway, self.issuer):
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)


def launch_pair(
    gateway_argv: Sequence[str],
    *,
    cwd: str,
    env: dict[str, str] | None = None,
) -> SupervisedPair:
    plugin_endpoint, issuer_endpoint = socket.socketpair()
    try:
        issuer = spawn_with_capability(
            [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.issuer_stub"],
            issuer_endpoint,
            cwd=cwd,
            env=env,
        )
        gateway = spawn_with_capability(gateway_argv, plugin_endpoint, cwd=cwd, env=env)
    except BaseException:
        if "issuer" in locals() and issuer.poll() is None:
            issuer.terminate()
            issuer.wait(timeout=2.0)
        raise
    finally:
        plugin_endpoint.close()
        issuer_endpoint.close()
    return SupervisedPair(issuer=issuer, gateway=gateway)


def supervise_forever(gateway_argv: Sequence[str], *, cwd: str, env: dict[str, str]) -> int:
    pair = launch_pair(gateway_argv, cwd=cwd, env=env)
    try:
        while pair.gateway.poll() is None and pair.issuer.poll() is None:
            time.sleep(0.2)
        return pair.gateway.returncode or pair.issuer.returncode or 0
    finally:
        pair.stop()
