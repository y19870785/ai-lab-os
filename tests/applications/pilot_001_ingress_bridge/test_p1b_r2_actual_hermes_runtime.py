"""PILOT-001-P1B-R2 actual Hermes gateway.run runtime-entry validation.

R2 closes the precision gap left by R1: the R1 explicit test entered a
repository-controlled stub module, which proves the bootstrap wiring but
not that the real Hermes gateway.run runtime is entered.  This file runs
the actual Hermes Python with the default gateway_module="gateway.run"
through the launcher path and requires runtime-entry evidence:

  actual executable      = Hermes venv python
  requested module       = gateway.run
  evidence.module        = gateway.run
  evidence.pid           = spawned Popen pid
  evidence.dumpable      = 0
  evidence.stage         = entering
  kernel mem observation = expected denial (EACCES/EPERM)
  process alive after evidence established

No Hermes source is modified, no business mutation occurs, and the
gateway is terminated by the runner right after runtime-entry evidence
(runtime_entry_only=True).  This proves RUNTIME_ENTRY_PROVEN, not a full
gateway service lifecycle.
"""

from __future__ import annotations

import errno
import json
import os
import subprocess
from pathlib import Path

import pytest

from applications.pilot_001_ingress_bridge.launcher import (
    RUNTIME_EVIDENCE_ENV,
    build_gateway_command,
    observe_kernel_dumpable,
    run_actual_gateway,
)

ROOT = Path(__file__).resolve().parents[3]
ACTUAL_HERMES_PY = "/home/hechao/.hermes/hermes-agent/venv/bin/python"
ACTUAL_HERMES_HOME = "/home/hechao/.hermes"


def _project_root(tmp_path: Path) -> Path:
    project = tmp_path / "ai-lab-pilot-001-p1a-r2"
    project.mkdir()
    (project / "config.yaml").write_text(
        "platforms:\n  wecom:\n    enabled: true\n", encoding="utf-8"
    )
    return project


def test_p1b_r2_default_command_targets_gateway_run():
    """Contract: the default launcher command targets gateway.run."""

    command = build_gateway_command(ACTUAL_HERMES_PY)
    assert command[0] == ACTUAL_HERMES_PY
    assert command[1].endswith("process_isolation.py")
    assert command[2:] == ["--module", "gateway.run"]


@pytest.mark.parametrize("errno_value", [errno.EACCES, errno.EPERM])
def test_p1b_r2_kernel_observation_expected_denial_passes(
    errno_value, monkeypatch
):
    """Expected denial errnos (EACCES/EPERM) prove isolation."""

    if os.name != "posix" or not Path("/proc/self/mem").exists():
        pytest.skip("kernel observation requires Linux /proc")

    def fake_open(path, flags):
        raise OSError(errno_value, "denied")

    monkeypatch.setattr(os, "open", fake_open)
    assert observe_kernel_dumpable(os.getpid()) == 0


@pytest.mark.parametrize("errno_value", [errno.ENOENT, errno.EIO, errno.ENOTDIR])
def test_p1b_r2_kernel_observation_unexpected_errno_fails_closed(
    errno_value, monkeypatch
):
    """Unexpected errnos must fail closed, never be read as isolation PASS."""

    if os.name != "posix" or not Path("/proc/self/mem").exists():
        pytest.skip("kernel observation requires Linux /proc")

    def fake_open(path, flags):
        raise OSError(errno_value, "unexpected")

    monkeypatch.setattr(os, "open", fake_open)
    with pytest.raises(RuntimeError, match="KERNEL_OBSERVATION_UNEXPECTED"):
        observe_kernel_dumpable(os.getpid())


def test_p1b_r2_kernel_observation_success_fails_closed(monkeypatch):
    """A successful /proc/<pid>/mem open means NOT isolated: fail closed."""

    if os.name != "posix" or not Path("/proc/self/mem").exists():
        pytest.skip("kernel observation requires Linux /proc")

    def fake_open(path, flags):
        return 7

    monkeypatch.setattr(os, "open", fake_open)
    with pytest.raises(RuntimeError, match="KERNEL_MEM_ACCESSIBLE"):
        observe_kernel_dumpable(os.getpid())


@pytest.mark.skipif(
    os.name != "posix" or os.environ.get("PILOT001_RUN_REAL_CAPABILITY_ATTACK") != "1",
    reason="authoritative P1B-R2 actual Hermes runtime entry requires explicit Linux run",
)
def test_p1b_r2_actual_hermes_gateway_run_runtime_entry_on_wsl2(
    tmp_path, monkeypatch
):
    """ACTUAL HERMES RUNTIME ENTRY: real gateway.run through the launcher path.

    Uses the real Hermes Python and the default gateway_module="gateway.run"
    (no stub).  The launcher verifies:

      - spawned executable is the actual Hermes Python
      - requested module == gateway.run
      - evidence.module == gateway.run
      - evidence.pid == spawned pid
      - evidence.dumpable == 0
      - evidence.stage == entering
      - kernel mem observation is the expected denial
      - the process is still alive after the evidence was established

    runtime_entry_only=True makes the runner terminate the long-lived
    gateway right after the entry evidence is verified.
    """

    if not Path(ACTUAL_HERMES_PY).is_file():
        pytest.skip("actual Hermes Python not present in this environment")
    called: dict[str, object] = {}

    original_popen = subprocess.Popen

    def spy_popen(command, **kwargs):
        called["popen"] = list(command)
        process = original_popen(command, **kwargs)
        called["popen_pid"] = process.pid
        return process

    monkeypatch.setattr(subprocess, "Popen", spy_popen)
    project = _project_root(tmp_path)
    environ = os.environ.copy()
    environ["HERMES_HOME"] = str(project / ".hermes-home")
    environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "1"
    evidence_file = project / ".pilot001-runtime-evidence.json"
    environ[RUNTIME_EVIDENCE_ENV] = str(evidence_file)

    from applications.pilot_001_ingress_bridge.launcher import (
        cleanup_temporary_project,
        prepare_temporary_project,
    )

    project = prepare_temporary_project(
        source_hermes_home=Path(ACTUAL_HERMES_HOME),
        mcp_command=[ACTUAL_HERMES_PY, "-m", "pilot_mcp"],
        root=project,
    )
    try:
        run_actual_gateway(
            ACTUAL_HERMES_PY,
            project=project,
            environ=environ,
            evidence_file=evidence_file,
            gateway_module="gateway.run",
            runtime_entry_only=True,
        )

        popen_cmd = called["popen"]
        assert popen_cmd[0] == ACTUAL_HERMES_PY
        assert popen_cmd[1].endswith("process_isolation.py")
        assert popen_cmd[2:] == ["--module", "gateway.run"]
        pid = called["popen_pid"]
        assert isinstance(pid, int) and pid > 0

        recorded = json.loads(evidence_file.read_text(encoding="utf-8"))
        assert recorded["pid"] == pid
        assert recorded["module"] == "gateway.run"
        assert recorded["dumpable"] == 0
        assert recorded["stage"] == "entering"
    finally:
        cleanup_temporary_project(project)
