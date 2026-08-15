"""Prepare and clean a temporary Hermes project for the internal P1A pilot."""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import yaml

EXPECTED_MODEL_TOOL_SUFFIXES = (
    "ai_lab_interaction_preview",
    "ai_lab_interaction_status",
    "ai_lab_interaction_view",
    "ai_lab_interaction_confirm",
)
EXPECTED_MODEL_TOOL_NAMES = tuple(
    f"mcp__ai_lab_p1a__{name}" for name in EXPECTED_MODEL_TOOL_SUFFIXES
)
FORBIDDEN_MODEL_TOOL_TOKENS = (
    "terminal", "process", "shell", "powershell", "python", "computer",
    "browser", "write_file", "patch", "install", "execute", "verify",
    "recover", "approve", "tool_search", "tool_call", "tool_describe",
)
RUNTIME_EVIDENCE_ENV = "PILOT001_RUNTIME_EVIDENCE_FILE"


def build_gateway_command(hermes_python: str, *, module: str = "gateway.run") -> list[str]:
    """Start the temporary gateway without touching the installed service unit.

    P1B: the final Hermes Python process must harden itself (PR_SET_DUMPABLE=0)
    and only then enter the gateway runtime.  Hardening the launcher and then
    exec-ing Hermes would be reset by the exec boundary, so the bootstrap
    module is the actual Python entry point and enters gateway.run via runpy
    inside the same final process (no further exec).

    module is the runtime module to enter after hardening; the default is
    Hermes gateway.run.  Pilot tests may pass a local stub module so the
    same launch path can be exercised end-to-end without touching Hermes.
    """

    executable = hermes_python.strip()
    if not executable:
        raise ValueError("Hermes Python executable is required")
    # `hermes gateway run` refreshes the installed systemd unit on startup.
    # A temporary HERMES_HOME must bypass that CLI self-heal path.
    bootstrap = Path(__file__).with_name("process_isolation.py")
    return [executable, str(bootstrap), "--module", module]


def enforce_model_tool_profile(tool_names: list[str]) -> None:
    """Fail closed unless the Hermes-visible namespace is exactly four tools."""

    if set(tool_names) != set(EXPECTED_MODEL_TOOL_NAMES) or len(tool_names) != 4:
        raise RuntimeError(
            "INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN: "
            + json.dumps(sorted(tool_names), separators=(",", ":"))
        )
    lowered = [name.casefold() for name in tool_names]
    if any(token in name for token in FORBIDDEN_MODEL_TOOL_TOKENS for name in lowered):
        raise RuntimeError(
            "INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN: forbidden token in namespace"
        )


def resolve_hermes_model_tools(
    hermes_python: str, *, project: Path, environ: dict[str, str]
) -> list[str]:
    """Ask the installed Hermes runtime for its actual WeCom model namespace."""

    probe = Path(__file__).with_name("hermes_tool_probe.py")
    completed = subprocess.run(
        [hermes_python, str(probe)],
        cwd=project,
        env=environ,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        names = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN") from exc
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise RuntimeError("INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN")
    if not names:
        diagnostic = completed.stderr.strip()[-2000:]
        mcp_log = project / ".hermes-home" / "logs" / "mcp-stderr.log"
        if mcp_log.is_file():
            diagnostic += "\nMCP stderr:\n" + mcp_log.read_text(
                encoding="utf-8", errors="replace"
            )[-4000:]
        raise RuntimeError(
            "INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN: empty Hermes namespace; "
            + diagnostic
        )
    return names


def run_pilot_gateway(
    *,
    source_hermes_home: Path,
    hermes_python: str,
    mcp_command: list[str],
    gateway_module: str = "gateway.run",
    runtime_entry_only: bool = False,
) -> None:
    """Prepare, resolve, gate, then and only then start the Pilot gateway."""

    project = prepare_temporary_project(
        source_hermes_home=source_hermes_home,
        mcp_command=mcp_command,
    )
    environ = os.environ.copy()
    environ.update(
        {
            "HERMES_HOME": str(project / ".hermes-home"),
            "HERMES_ENABLE_PROJECT_PLUGINS": "1",
        }
    )
    evidence_file = project / ".pilot001-runtime-evidence.json"
    environ[RUNTIME_EVIDENCE_ENV] = str(evidence_file)
    try:
        names = resolve_hermes_model_tools(
            hermes_python, project=project, environ=environ
        )
        enforce_model_tool_profile(names)
        print("INTERNAL_PILOT_TOOL_ALLOWLIST_EXACT", flush=True)
        verify_pilot_process_isolation(hermes_python, project=project, environ=environ)
        print("PILOT_PROCESS_ISOLATION_LINK_VERIFIED", flush=True)
        run_actual_gateway(
            hermes_python, project=project, environ=environ,
            evidence_file=evidence_file,
            gateway_module=gateway_module,
            runtime_entry_only=runtime_entry_only,
        )
    finally:
        cleanup_temporary_project(project)


def run_actual_gateway(
    hermes_python: str,
    *,
    project: Path,
    environ: dict[str, str],
    evidence_file: Path,
    gateway_module: str = "gateway.run",
    runtime_entry_only: bool = False,
) -> None:
    """Start the real hardened gateway and verify actual runtime evidence.

    The launcher spawns the final Hermes Python process (bootstrap) and waits
    for the target module's first execution frame to record its process
    identity and resolved filename in the evidence file.
    The recorded PID must equal the spawned gateway PID, proving the process
    that applied the isolation is the same process that enters the gateway
    module.  The evidence module field must equal the requested module so a
    stub can never be mistaken for gateway.run.  The kernel-enforced
    isolation is then observed from this (different) process: opening
    /proc/<pid>/mem must fail with an expected denial errno.

    A pre-call ``dispatching`` event is never accepted.  The evidence stage
    must be ``module_started``, the resolved source must match the requested
    module (and, for gateway.run, belong to the Hermes installation), and the
    process must remain alive: that is the runtime-entry proof.

    With runtime_entry_only=True the gateway is terminated right after the
    runtime-entry evidence is verified, so a long-lived Hermes gateway can
    be acceptance-tested without waiting for its full service lifecycle.
    """

    command = build_gateway_command(hermes_python, module=gateway_module)
    gateway = subprocess.Popen(
        command,
        cwd=project,
        env=environ,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        evidence = wait_for_runtime_evidence(
            evidence_file, gateway_pid=gateway.pid, gateway=gateway,
        )
        recorded_pid = evidence.get("pid")
        recorded_dumpable = evidence.get("dumpable")
        recorded_pr_get_dumpable = evidence.get("pr_get_dumpable")
        recorded_stage = evidence.get("stage")
        recorded_module = evidence.get("module")
        recorded_filename = evidence.get("filename")
        if recorded_pid != gateway.pid:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_PID_MISMATCH: evidence pid="
                + str(recorded_pid)
                + " gateway pid="
                + str(gateway.pid)
            )
        if recorded_module != gateway_module:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_MODULE_MISMATCH: evidence module="
                + str(recorded_module)
                + " expected="
                + gateway_module
            )
        if recorded_dumpable != 0:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_NOT_ISOLATED: dumpable="
                + str(recorded_dumpable)
            )
        if recorded_pr_get_dumpable != 0:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_PR_GET_DUMPABLE_INVALID: value="
                + str(recorded_pr_get_dumpable)
            )
        if recorded_stage != "module_started":
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_WRONG_STAGE: stage="
                + str(recorded_stage)
            )
        validate_runtime_module_filename(
            recorded_filename,
            module=gateway_module,
            hermes_python=hermes_python,
        )
        if gateway.poll() is not None:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_EXITED_EARLY: returncode="
                + str(gateway.returncode)
            )
        # Do not let a target that exits immediately after emitting its first
        # frame race the parent-side liveness check.
        time.sleep(0.1)
        if gateway.poll() is not None:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_EXITED_EARLY: returncode="
                + str(gateway.returncode)
            )
        kernel_dumpable = observe_kernel_dumpable(gateway.pid)
        if kernel_dumpable != 0:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_KERNEL_NOT_ISOLATED: /proc dumpable="
                + str(kernel_dumpable)
            )
        print(
            "PILOT_ACTUAL_RUNTIME_EVIDENCE pid="
            + str(gateway.pid)
            + " module="
            + gateway_module
            + " stage="
            + str(recorded_stage)
            + " filename="
            + str(recorded_filename)
            + " PR_GET_DUMPABLE=0 dumpable=0 kernel_dumpable=0"
            + " proc_status="
            + str(gateway.pid),
            flush=True,
        )
        if runtime_entry_only:
            return
        returncode = gateway.wait()
        if returncode != 0:
            raise RuntimeError(
                "PILOT_GATEWAY_EXITED_NONZERO: returncode=" + str(returncode)
            )
    finally:
        if gateway.poll() is None:
            gateway.terminate()
            try:
                gateway.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                gateway.kill()
                gateway.wait(timeout=2.0)


def wait_for_runtime_evidence(
    evidence_file: Path,
    *,
    gateway_pid: int,
    gateway: subprocess.Popen | None = None,
    timeout: float = 30.0,
) -> dict[str, object]:
    """Wait for the bootstrap to record process identity evidence.

    The evidence file must appear (written by the same final process after
    hardening is applied) and must name the spawned gateway PID.  This is
    the process identity linkage: the process that applied the isolation
    is the process that entered the gateway runtime.
    """

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = evidence_file.read_text(encoding="utf-8")
        except OSError:
            if gateway is not None and gateway.poll() is not None:
                raise RuntimeError(
                    "PILOT_ACTUAL_RUNTIME_EXITED_BEFORE_MODULE_START: returncode="
                    + str(gateway.returncode)
                    + " last_stage=missing"
                )
            time.sleep(0.05)
            continue
        try:
            evidence = json.loads(raw)
        except json.JSONDecodeError:
            if gateway is not None and gateway.poll() is not None:
                raise RuntimeError(
                    "PILOT_ACTUAL_RUNTIME_EXITED_BEFORE_MODULE_START: returncode="
                    + str(gateway.returncode)
                    + " last_stage=invalid"
                )
            time.sleep(0.05)
            continue
        if not isinstance(evidence, dict):
            raise TypeError("PILOT_ACTUAL_RUNTIME_EVIDENCE_INVALID")
        if evidence.get("pid") != gateway_pid:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_PID_MISMATCH: evidence pid="
                + str(evidence.get("pid"))
                + " gateway pid="
                + str(gateway_pid)
            )
        if evidence.get("stage") == "module_started":
            return evidence
        if gateway is not None and gateway.poll() is not None:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_EXITED_BEFORE_MODULE_START: returncode="
                + str(gateway.returncode)
                + " last_stage="
                + str(evidence.get("stage"))
            )
        time.sleep(0.05)
    raise RuntimeError(
        "PILOT_ACTUAL_RUNTIME_EVIDENCE_MISSING: no evidence from pid="
        + str(gateway_pid)
    )


def validate_runtime_module_filename(
    filename: object, *, module: str, hermes_python: str
) -> Path:
    """Fail closed unless evidence names the requested module's real file."""

    if not isinstance(filename, str) or not filename:
        raise RuntimeError("PILOT_ACTUAL_RUNTIME_FILENAME_MISSING")
    resolved = Path(filename).resolve()
    module_parts = module.split(".")
    expected_tail = tuple(module_parts[:-1]) + (module_parts[-1] + ".py",)
    if (
        tuple(resolved.parts[-len(expected_tail):]) != expected_tail
        or not resolved.is_file()
    ):
        raise RuntimeError(
            "PILOT_ACTUAL_RUNTIME_FILENAME_MISMATCH: filename="
            + str(resolved)
            + " module="
            + module
        )
    if module == "gateway.run":
        # Keep the invoked Hermes path rather than resolving its Python
        # symlink into .hermes-runtime generations.  The stable installation
        # root is the parent of <hermes-agent>/venv.
        hermes_venv = Path(hermes_python).absolute().parent.parent
        hermes_install = hermes_venv.parent
        try:
            resolved.relative_to(hermes_install)
        except ValueError as exc:
            raise RuntimeError(
                "PILOT_ACTUAL_RUNTIME_NOT_HERMES_GATEWAY: filename="
                + str(resolved)
                + " hermes_install="
                + str(hermes_install)
            ) from exc
    return resolved


# errno values that are the expected kernel denial for a non-dumpable
# /proc/<pid>/mem cross-process open under the tested profile.
KERNEL_DENIAL_ERRNOS = (errno.EACCES, errno.EPERM)


def observe_kernel_dumpable(pid: int) -> int:
    """Observe the kernel-enforced isolation of a live process.

    Independent of the bootstrap's own prctl introspection: opens
    /proc/<pid>/mem from this (different, same-UID) process.  When the
    target is non-dumpable the kernel refuses the access with an expected
    denial errno (EACCES or EPERM); when dumpable=1 the open succeeds.

    The observation is strict: only the expected denial errnos prove
    KERNEL_ACCESS_DENIED_AS_EXPECTED.  Any other OSError (process gone,
    path missing, I/O failure, unsupported proc state) fails closed with
    a diagnostic; a successful open fails as not isolated.
    """

    if os.name != "posix" or not Path(f"/proc/{pid}/mem").is_file():
        raise RuntimeError(
            "PILOT_ACTUAL_RUNTIME_KERNEL_OBSERVATION_UNSUPPORTED: "
            + "linux /proc required"
        )
    try:
        fd = os.open(f"/proc/{pid}/mem", os.O_RDONLY)
    except OSError as exc:
        if exc.errno in KERNEL_DENIAL_ERRNOS:
            return 0
        raise RuntimeError(
            "PILOT_ACTUAL_RUNTIME_KERNEL_OBSERVATION_UNEXPECTED: "
            + f"errno={exc.errno} ({exc.strerror}) pid={pid}"
        ) from exc
    os.close(fd)
    raise RuntimeError(
        "PILOT_ACTUAL_RUNTIME_KERNEL_MEM_ACCESSIBLE: "
        + f"gateway process is dumpable (open /proc/{pid}/mem succeeded)"
    )


def verify_pilot_process_isolation(
    hermes_python: str, *, project: Path, environ: dict[str, str]
) -> None:
    """Fail closed unless the final-process hardening link is effective.

    Runs the same bootstrap the gateway will use in --check mode: it must
    apply PR_SET_DUMPABLE=0 and prove PR_GET_DUMPABLE==0 in a real Python
    process before the gateway is allowed to start.
    """

    bootstrap = Path(__file__).with_name("process_isolation.py")
    # check=False is deliberate: the return code is validated below and a
    # non-zero self-check must produce PILOT_PROCESS_ISOLATION_UNPROVEN, not
    # a bare CalledProcessError, so the gateway fails closed with evidence.
    completed = subprocess.run(
        [hermes_python, str(bootstrap), "--check"],
        cwd=project,
        env=environ,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or (
        "PILOT_PROCESS_ISOLATION_EFFECTIVE PR_GET_DUMPABLE=0"
        not in completed.stdout
    ):
        diagnostic = (completed.stdout + "\n" + completed.stderr).strip()[-2000:]
        raise RuntimeError(
            "PILOT_PROCESS_ISOLATION_UNPROVEN: "
            + (diagnostic or "hardening self-check failed")
        )


def prepare_temporary_project(
    *, source_hermes_home: Path, mcp_command: list[str], root: Path | None = None,
) -> Path:
    """Project the plugin and a narrowed config without touching live discovery."""

    project = root or Path(tempfile.mkdtemp(prefix="ai-lab-pilot-001-p1a-"))
    project.mkdir(parents=True, exist_ok=True)
    hermes_home = project / ".hermes-home"
    hermes_home.mkdir(mode=0o700)
    source_config = source_hermes_home / "config.yaml"
    config = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    for platform_name, platform_config in (config.get("platforms") or {}).items():
        if isinstance(platform_config, dict):
            platform_config["enabled"] = platform_name == "wecom"
    # Project plugins are opt-in.  This key matches the required nested
    # projection path (<project>/.hermes/plugins/platforms/wecom), allowing
    # its concrete adapter registration to replace Hermes' deferred bundled
    # WeCom registration for this temporary project only.
    config["plugins"] = {"enabled": ["platforms/wecom"]}
    config["platform_toolsets"] = {"wecom": ["ai-lab-p1a"]}
    config.setdefault("tools", {})["tool_search"] = {"enabled": "off"}
    config["mcp_servers"] = {
        "ai-lab-p1a": {
            "command": mcp_command[0],
            "args": mcp_command[1:],
            "enabled": True,
            "tools": {
                "include": list(EXPECTED_MODEL_TOOL_SUFFIXES),
                "resources": False,
                "prompts": False,
            },
        }
    }
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    for name in ("auth.json",):
        source = source_hermes_home / name
        if source.is_file():
            shutil.copy2(source, hermes_home / name)
    source_env = source_hermes_home / ".env"
    if source_env.is_file():
        blocked_platform_prefixes = (
            "TELEGRAM_", "DISCORD_", "SLACK_", "WHATSAPP_", "WEIXIN_",
            "FEISHU_", "LINE_", "SIGNAL_", "MATRIX_",
        )
        retained = []
        for line in source_env.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if not any(key.startswith(prefix) for prefix in blocked_platform_prefixes):
                retained.append(line)
        (hermes_home / ".env").write_text("\n".join(retained) + "\n", encoding="utf-8")
    template = Path(__file__).parent / "plugin_template" / "platforms" / "wecom"
    destination = project / ".hermes" / "plugins" / "platforms" / "wecom"
    shutil.copytree(template, destination)
    return project


def cleanup_temporary_project(project: Path) -> None:
    """Remove only a launcher-created, positively identified temporary root."""

    resolved = project.resolve()
    if not resolved.name.startswith("ai-lab-pilot-001-p1a-"):
        raise RuntimeError("refusing to remove an unrecognized project root")
    shutil.rmtree(resolved)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-tools")
    verify.add_argument("tools", nargs="*")
    start = subparsers.add_parser("start-gateway")
    start.add_argument("--source-hermes-home", type=Path, required=True)
    start.add_argument("--hermes-python", required=True)
    start.add_argument("mcp_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "verify-tools":
        enforce_model_tool_profile(args.tools)
        print("INTERNAL_PILOT_TOOL_ALLOWLIST_EXACT")
    else:
        mcp_command = list(args.mcp_command)
        if mcp_command[:1] == ["--"]:
            mcp_command.pop(0)
        if not mcp_command:
            parser.error("start-gateway requires MCP argv after --")
        run_pilot_gateway(
            source_hermes_home=args.source_hermes_home,
            hermes_python=args.hermes_python,
            mcp_command=mcp_command,
        )


if __name__ == "__main__":
    main()
