"""PILOT-001-P1B-R1 actual runtime evidence closure tests.

R1 closes the gap between the controlled validation holder (gateway_probe)
and the actual launcher-started Hermes gateway runtime by proving, from the
real run_pilot_gateway() path, that:

  launcher
    -> actual Hermes Python process
    -> process_isolation bootstrap
    -> required isolation applied (PR_SET_DUMPABLE=0)
    -> same process enters gateway.run (stub gateway in tests)

The process identity linkage is the evidence file written by the bootstrap
inside the final process: its pid must equal the pid of the process spawned
by the launcher, and the kernel-visible dumpable state read from
/proc/<pid>/status must be 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from applications.pilot_001_ingress_bridge.launcher import (
    RUNTIME_EVIDENCE_ENV,
    build_gateway_command,
    run_actual_gateway,
    wait_for_runtime_evidence,
)

ROOT = Path(__file__).resolve().parents[3]
STUB_GATEWAY = "tests.applications.pilot_001_ingress_bridge.stub_gateway_runtime"


def test_p1b_r1_bootstrap_enters_stub_gateway_and_records_identity(tmp_path):
    """Windows non-real: assert the bootstrap->module linkage contract.

    This cannot apply Linux prctl on Windows, so it verifies the launcher
    wiring statically: the gateway command goes through the bootstrap, and
    the stub gateway (the module the runtime enters) is the same module the
    bootstrap is asked to run.  The authoritative Linux/WSL2 run is the
    explicit test below.
    """

    command = build_gateway_command("/opt/hermes/python", module=STUB_GATEWAY)
    assert command[0] == "/opt/hermes/python"
    assert command[1].endswith("process_isolation.py")
    assert command[2:] == ["--module", STUB_GATEWAY]
    default_command = build_gateway_command("/opt/hermes/python")
    assert default_command[2:] == ["--module", "gateway.run"]
    stub = Path(__file__).with_name("stub_gateway_runtime.py")
    assert stub.is_file()
    source = stub.read_text(encoding="utf-8")
    assert "PILOT001_RUNTIME_EVIDENCE_FILE" in source
    assert "os.getpid()" in source


def test_p1b_r1_wait_for_runtime_evidence_requires_matching_pid(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps({"pid": 999, "dumpable": 0, "stage": "entering"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="EVIDENCE_MISSING"):
        wait_for_runtime_evidence(evidence, gateway_pid=1234, timeout=0.2)


def test_p1b_r1_wait_for_runtime_evidence_accepts_matching_pid(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps({"pid": 1234, "dumpable": 0, "stage": "entering"}),
        encoding="utf-8",
    )
    result = wait_for_runtime_evidence(evidence, gateway_pid=1234, timeout=1.0)
    assert result["pid"] == 1234
    assert result["dumpable"] == 0

@pytest.mark.skipif(
    os.name != "posix" or os.environ.get("PILOT001_RUN_REAL_CAPABILITY_ATTACK") != "1",
    reason="authoritative P1B-R1 actual runtime link requires explicit Linux run",
)
def test_p1b_r1_actual_gateway_link_on_wsl2(tmp_path, monkeypatch):
    """Real launcher runtime path: actual process enters the gateway module.

    Exercises run_actual_gateway() (the launcher's real gateway-spawn path,
    used by run_pilot_gateway after the tool-profile gate) end-to-end on
    Linux/WSL2 with the stub gateway as the module.  The bootstrap applies
    hardening in the final Python process, writes evidence naming its own
    pid, then enters the stub via runpy inside the same process.  The
    launcher verifies evidence.pid == spawned pid and observes
    /proc/<pid>/status Dumpable: 0 from the kernel.
    """

    called: dict[str, object] = {}

    original_run = subprocess.run

    def spy_run(command, **kwargs):
        called["run"] = list(command)
        return original_run(command, **kwargs)

    original_popen = subprocess.Popen

    def spy_popen(command, **kwargs):
        called["popen"] = list(command)
        process = original_popen(command, **kwargs)
        called["popen_pid"] = process.pid
        return process

    monkeypatch.setattr(subprocess, "run", spy_run)
    monkeypatch.setattr(subprocess, "Popen", spy_popen)
    project = tmp_path / "pilot-project"
    project.mkdir()
    (project / "config.yaml").write_text(
        "platforms:\n  wecom:\n    enabled: true\n", encoding="utf-8"
    )
    environ = os.environ.copy()
    environ["HERMES_HOME"] = str(project)
    environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "1"
    # Allow the stub gateway module (under tests/) to be imported by the
    # bootstrap through runpy, as gateway.run would be from the Hermes
    # site-packages in the real deployment.
    environ["PYTHONPATH"] = str(ROOT) + os.pathsep + environ.get("PYTHONPATH", "")
    evidence_file = project / ".pilot001-runtime-evidence.json"
    environ[RUNTIME_EVIDENCE_ENV] = str(evidence_file)
    run_actual_gateway(
        sys.executable,
        project=project,
        environ=environ,
        evidence_file=evidence_file,
        gateway_module=STUB_GATEWAY,
    )
    # The launcher must have spawned the gateway through the bootstrap.
    popen_cmd = called["popen"]
    assert popen_cmd[0] == sys.executable
    assert popen_cmd[1].endswith("process_isolation.py")
    assert popen_cmd[2:] == ["--module", STUB_GATEWAY]
    pid = called["popen_pid"]
    assert isinstance(pid, int) and pid > 0
    # Evidence written by the bootstrap inside the final process must name
    # the spawned pid: the process that applied isolation is the process
    # that ran the gateway runtime.
    recorded = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert recorded["pid"] == pid
    assert recorded["dumpable"] == 0
    assert recorded["module"] == STUB_GATEWAY
    # The runtime completed inside the same process: the bootstrap wrote
    # the "returned" stage after runpy returned, still naming the same pid.
    assert recorded["stage"] == "returned"
    # Kernel observation was performed by the launcher while the gateway
    # process was alive (observe_kernel_dumpable inside run_actual_gateway);
    # re-observing after exit is impossible, so this is asserted through
    # the launcher path having completed without raising.
