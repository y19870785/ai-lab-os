"""PILOT-001-P1B active process-isolation attack acceptance."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests.spike.pilot_001_ingress_capability.supervisor import (
    spawn_with_capability,
)

ROOT = Path(__file__).resolve().parents[2]


def _run_isolated_attack() -> tuple[dict[str, object], dict[str, object]]:
    plugin_endpoint, issuer_endpoint = socket.socketpair()
    env = os.environ.copy()
    env["PILOT001_REQUIRE_PROCESS_ISOLATION"] = "1"
    issuer = spawn_with_capability(
        [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.issuer_stub"],
        issuer_endpoint,
        cwd=str(ROOT),
        env=env,
    )
    gateway = spawn_with_capability(
        [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.gateway_probe"],
        plugin_endpoint,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    plugin_endpoint.close()
    issuer_endpoint.close()
    try:
        assert gateway.stdout is not None
        holder = json.loads(gateway.stdout.readline())
        attacker = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.spike.pilot_001_ingress_capability.attack_probe",
                str(gateway.pid),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return holder, json.loads(attacker.stdout)
    finally:
        gateway.terminate()
        issuer.terminate()
        gateway.wait(timeout=5.0)
        issuer.wait(timeout=5.0)


def _assert_isolated_result(
    holder: dict[str, object], attack: dict[str, object]
) -> None:
    assert holder["receipt_accepted"] is True
    assert holder["child"] == {"fd_visible": False}
    assert holder["hardening"] == {
        "startup": 0,
        "capability_acquired": 0,
        "post_child": 0,
    }
    assert attack["fd_in_environment"] is False
    assert attack["fd_in_argv"] is False
    assert attack["proc_duplicated"] is False
    assert attack["pidfd_getfd"]["duplicated"] is False
    assert attack["pidfd_getfd"]["invoked"] is False
    assert attack["pidfd_getfd"]["errno"] == 1


def test_p1b_process_local_non_dumpable_denies_same_uid_attack() -> None:
    if os.name != "posix" or os.environ.get("PILOT001_RUN_REAL_CAPABILITY_ATTACK") != "1":
        pytest.skip("authoritative P1B attack acceptance requires explicit Linux run")
    _assert_isolated_result(*_run_isolated_attack())


def test_p1b_restart_reapplies_hardening_and_denies_replay() -> None:
    if os.name != "posix" or os.environ.get("PILOT001_RUN_REAL_CAPABILITY_ATTACK") != "1":
        pytest.skip("authoritative P1B restart acceptance requires explicit Linux run")
    first = _run_isolated_attack()
    second = _run_isolated_attack()
    _assert_isolated_result(*first)
    _assert_isolated_result(*second)
