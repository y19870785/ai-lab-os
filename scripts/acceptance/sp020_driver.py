"""Executable ACC-020 Windows evidence driver.

The driver supports preparation, an explicitly non-formal rehearsal, and a
future formal run against an independently frozen implementation Head.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCENARIOS = tuple("ABCDEFGHIJKLMNOPQRSTUV")
HARNESS_FAILURE = "INVALID_ACCEPTANCE_HARNESS"
PRODUCT_FAILURE = "PRODUCT_ACCEPTANCE_FAILED"


class HarnessError(RuntimeError):
    """The evidence environment cannot support a valid acceptance run."""


class ProductAcceptanceError(RuntimeError):
    """The product did not satisfy an executed acceptance assertion."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_manifest(root: Path) -> list[dict[str, object]]:
    if not root.exists():
        return []
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def run_command(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    records: list[dict[str, object]],
    timeout: int = 120,
) -> dict[str, object]:
    """Run, record, and fail on a non-zero acceptance helper command."""

    started = datetime.now(UTC)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    record = {
        "command": command,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }
    records.append(record)
    if result.returncode != 0:
        raise ProductAcceptanceError(
            f"command exited with {result.returncode}: {command[0]}"
        )
    return record


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise HarnessError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _empty_or_missing(path: Path) -> bool:
    return not path.exists() or (
        path.is_dir() and next(path.iterdir(), None) is None
    )


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _is_windows() -> bool:
    """Keep the real ACC-020 platform gate injectable for harness tests."""

    return os.name == "nt"


def validate_harness(args: argparse.Namespace, driver: Path) -> dict[str, str]:
    if not _is_windows():
        raise HarnessError("ACC-020 requires Windows")
    repo = args.repository_root.resolve()
    if not args.repository_root.is_absolute() or not (repo / ".git").exists():
        raise HarnessError("repository root must be an absolute Git checkout")
    head = _git(repo, "rev-parse", "HEAD")
    if head != args.frozen_head:
        raise HarnessError(f"frozen Head mismatch: expected {args.frozen_head}")
    if _git(repo, "status", "--porcelain"):
        raise HarnessError("repository working tree must be clean")
    actual_driver_hash = sha256(driver)
    if actual_driver_hash != args.expected_driver_sha256.lower():
        raise HarnessError("driver SHA-256 mismatch")

    source = args.source_data_root.resolve()
    restore = args.restore_data_root.resolve()
    evidence = args.evidence_dir.resolve()
    roots = (args.source_data_root, args.restore_data_root, args.evidence_dir)
    if any(not value.is_absolute() for value in roots):
        raise HarnessError("data and evidence roots must be absolute")
    if source == restore:
        raise HarnessError("source and restore roots must be distinct")
    if _contains(source, restore) or _contains(restore, source):
        raise HarnessError("source and restore roots must not be nested")
    checkout_default = (repo / "data").resolve()
    if source == checkout_default or restore == checkout_default:
        raise HarnessError("checkout default data directory is forbidden")
    if _contains(source, evidence) or _contains(restore, evidence):
        raise HarnessError("evidence directory must be outside hashed data roots")
    if not _empty_or_missing(source):
        raise HarnessError("source data root must be empty or absent")
    if not _empty_or_missing(restore):
        raise HarnessError("restore data root must be empty or absent")
    if not _port_is_free(args.api_port):
        raise HarnessError("API port is not free")
    if sys.version_info[:2] != (3, 12):
        raise HarnessError("ACC-020 requires Python 3.12")
    if os.getenv("AI_LAB_PROVIDER_MODE", "").strip().lower() not in {
        "mock",
        "test",
    }:
        raise HarnessError("provider mode must be explicit mock or test")
    if not os.getenv("AI_LAB_API_TOKEN", "").strip():
        raise HarnessError("API token must be configured")
    return {
        "head": head,
        "driver_sha256": actual_driver_hash,
        "source": str(source),
        "restore": str(restore),
        "evidence": str(evidence),
    }


def _base_manifest(
    args: argparse.Namespace,
    validated: dict[str, str],
) -> dict[str, Any]:
    prepare = args.prepare_only
    return {
        "schema_version": "acc-020-evidence-v1",
        "status": "PREPARED_NOT_EXECUTED" if prepare else "RUNNING",
        "execution_kind": (
            "PREPARE_ONLY"
            if prepare
            else "REHEARSAL / NOT_FORMAL_ACCEPTANCE"
            if args.rehearsal
            else "FORMAL_ACCEPTANCE"
        ),
        "frozen_head": args.frozen_head,
        "driver_sha256": validated["driver_sha256"],
        "python_version": sys.version,
        "utc_time": datetime.now(UTC).isoformat(),
        "windows_local_time": datetime.now().astimezone().isoformat(),
        "source_data_root": validated["source"],
        "restore_data_root": validated["restore"],
        "api_pid": None,
        "restart_api_pid": None,
        "restore_api_pid": None,
        "api_port": args.api_port,
        "config_summary": {
            "profile": "local-daily",
            "provider_mode": os.getenv("AI_LAB_PROVIDER_MODE"),
            "api_token": "configured",
        },
        "commands": [],
        "http_operations": [],
        "provider_spy_installed": False if prepare else None,
        "provider_spy_call_count": None,
        "source_manifest_before_restore": [],
        "source_manifest_after_restore": [],
        "restore_manifest": [],
        "mutations": [],
        "canonical_ids": [],
        "workspace": {},
        "revisions": [],
        "idempotency_keys": [],
        "claims_and_sagas": [],
        "confirmations": [],
        "event_bus": [],
        "scheduler_mutations": [],
        "health_snapshots": [],
        "connection_counts": [],
        "scenarios": {
            scenario: {
                "result": "NOT_MEASURED" if prepare else "PENDING",
                "evidence": [],
                "evidence_paths": [],
            }
            for scenario in SCENARIOS
        },
    }


def _write_manifest(path: Path, record: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _provider_spy(evidence: Path) -> tuple[Path, Path]:
    spy_root = evidence / "provider-spy"
    spy_root.mkdir(parents=True, exist_ok=True)
    counter = spy_root / "calls.log"
    counter.write_text("", encoding="utf-8")
    (spy_root / "sitecustomize.py").write_text(
        """import os
from pathlib import Path
from core.providers.llm.mock import MockLLMProvider
from core.providers.llm.openai import OpenAILLMProvider
from core.bus.bus import MemoryBus
from core.scheduler.runtime import SchedulerRuntime
_counter = Path(os.environ["ACC020_PROVIDER_SPY_FILE"])
_counter.with_name("installed").write_text("installed", encoding="utf-8")
_events = _counter.with_name("events.log")
_scheduler = _counter.with_name("scheduler.log")
def _wrap(original):
    async def counted(self, request):
        with _counter.open("a", encoding="utf-8") as stream:
            stream.write("call\\n")
        return await original(self, request)
    return counted
MockLLMProvider.generate = _wrap(MockLLMProvider.generate)
OpenAILLMProvider.generate = _wrap(OpenAILLMProvider.generate)
_publish = MemoryBus.publish
async def _record_publish(self, topic, event):
    with _events.open("a", encoding="utf-8") as stream:
        stream.write(f"{topic}\\n")
    return await _publish(self, topic, event)
MemoryBus.publish = _record_publish
_schedule = SchedulerRuntime.schedule
async def _record_schedule(self, request):
    with _scheduler.open("a", encoding="utf-8") as stream:
        stream.write(f"{request.job_name}\\n")
    return await _schedule(self, request)
SchedulerRuntime.schedule = _record_schedule
""",
        encoding="utf-8",
    )
    return spy_root, counter


def _runtime_env(
    args: argparse.Namespace,
    *,
    data_root: Path,
    spy_root: Path,
    counter: Path,
) -> dict[str, str]:
    env = dict(os.environ)
    repo = args.repository_root.resolve()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env.update({
        "PYTHONPATH": os.pathsep.join(
            value
            for value in (str(spy_root), str(repo), existing_pythonpath)
            if value
        ),
        "PYTHONUTF8": "1",
        "ACC020_PROVIDER_SPY_FILE": str(counter),
        "AI_LAB_PROFILE": "local-daily",
        "AI_LAB_DATA_DIR": str(data_root),
        "AI_LAB_SQLITE_DIR": str(data_root / "sqlite"),
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_ENABLE_USER_TASKS": "true",
        "AI_LAB_ENABLE_DAILY_REVIEW": "true",
        "AI_LAB_ENABLE_REMINDERS": "true",
        "AI_LAB_ENABLE_SCHEDULER": "true",
        "AI_LAB_ENABLE_KNOWLEDGE": "false",
        "AI_LAB_ENABLE_COORDINATION": "false",
        "AI_LAB_ENABLE_API": "true",
        "AI_LAB_API_AUTH_ENABLED": "true",
        "AI_LAB_API_BIND": "127.0.0.1",
        "AI_LAB_TENANT_ID": "acc020-tenant",
        "AI_LAB_WORKSPACE_ID": "acc020-workspace",
        "AI_LAB_NAMESPACE": "daily",
        "AI_LAB_SESSION_ID": "acc020-session",
        "AI_LAB_AGENT_ID": "acc020-driver",
        "AI_LAB_SCHEDULER_TICK_INTERVAL": "0.05",
    })
    return env


def _start_api(
    args: argparse.Namespace,
    *,
    env: dict[str, str],
    label: str,
    evidence: Path,
    record: dict[str, Any],
) -> tuple[subprocess.Popen[str], Any, Any]:
    stdout = (evidence / f"{label}-stdout.log").open(
        "w", encoding="utf-8"
    )
    stderr = (evidence / f"{label}-stderr.log").open(
        "w", encoding="utf-8"
    )
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.api_port),
    ]
    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    process = subprocess.Popen(
        command,
        cwd=args.repository_root,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        creationflags=creationflags,
    )
    record["commands"].append({
        "command": command,
        "started_at": datetime.now(UTC).isoformat(),
        "pid": process.pid,
        "label": label,
        "stdout_path": f"{label}-stdout.log",
        "stderr_path": f"{label}-stderr.log",
    })
    return process, stdout, stderr


def _stop_api(process: subprocess.Popen[str], stdout, stderr) -> int:
    if process.poll() is None:
        try:
            shutdown_signal = (
                signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT
            )
            process.send_signal(shutdown_signal)
            process.wait(timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    stdout.close()
    stderr.close()
    return int(process.returncode or 0)


def _assert_graceful_shutdown(
    *,
    exit_code: int,
    stderr_path: Path,
    label: str,
) -> None:
    """Accept Windows CTRL_BREAK=3 only with Uvicorn shutdown completion."""

    allowed = {0, 3} if os.name == "nt" else {0}
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    if (
        exit_code not in allowed
        or "Application shutdown complete." not in stderr_text
        or "Finished server process" not in stderr_text
    ):
        raise ProductAcceptanceError(
            f"{label} API did not shut down cleanly: {exit_code}"
        )


def _http(
    args: argparse.Namespace,
    record: dict[str, Any],
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, dict[str, Any]]:
    url = f"http://127.0.0.1:{args.api_port}{path}"
    payload = (
        json.dumps(body, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None
    )
    request_headers = {
        "Content-Type": "application/json",
        "X-Trace-ID": f"acc020-{len(record['http_operations']) + 1}",
    }
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    parsed = json.loads(raw) if raw else {}
    record["http_operations"].append({
        "method": method,
        "path": path,
        "status": status,
        "response_keys": sorted(parsed) if isinstance(parsed, dict) else [],
    })
    if status not in expected:
        raise ProductAcceptanceError(
            f"{method} {path} returned {status}, expected {expected}"
        )
    return status, parsed


def _poll_ready(
    args: argparse.Namespace,
    record: dict[str, Any],
    process: subprocess.Popen[str],
) -> None:
    deadline = time.monotonic() + 30
    last_error = "not started"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProductAcceptanceError(
                f"Uvicorn exited during startup with {process.returncode}"
            )
        try:
            _http(args, record, "GET", "/health/live")
            _http(args, record, "GET", "/health/ready")
            return
        except (OSError, ProductAcceptanceError) as exc:
            last_error = str(exc)
            time.sleep(0.2)
    raise ProductAcceptanceError(f"API readiness timeout: {last_error}")


def _pass(
    record: dict[str, Any],
    scenario: str,
    *evidence: str,
) -> None:
    record["scenarios"][scenario] = {
        "result": "PASS",
        "evidence": list(evidence),
        "evidence_paths": ["manifest.json"],
    }


def _execute(
    args: argparse.Namespace,
    record: dict[str, Any],
    manifest_path: Path,
) -> None:
    repo = args.repository_root.resolve()
    source = args.source_data_root.resolve()
    restore = args.restore_data_root.resolve()
    evidence = args.evidence_dir.resolve()
    source.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    spy_root, counter = _provider_spy(evidence)
    record["provider_spy_installed"] = True
    token = os.environ["AI_LAB_API_TOKEN"]
    now = datetime.now(UTC)
    workspace_headers = {
        "X-Tenant-ID": "acc020-tenant",
        "X-Workspace-ID": "acc020-workspace",
        "X-Namespace": "daily",
        "X-Session-ID": "acc020-session",
        "X-Agent-ID": "acc020-driver",
    }
    record["workspace"] = {
        key.removeprefix("X-").lower().replace("-", "_"): value
        for key, value in workspace_headers.items()
    }

    env = _runtime_env(
        args,
        data_root=source,
        spy_root=spy_root,
        counter=counter,
    )
    run_command(
        [sys.executable, "-m", "cli", "profile", "--require-local-daily"],
        env=env,
        cwd=repo,
        records=record["commands"],
    )
    if not (spy_root / "installed").exists():
        raise HarnessError("Provider spy was not installed")
    process, stdout, stderr = _start_api(
        args,
        env=env,
        label="source-api",
        evidence=evidence,
        record=record,
    )
    record["api_pid"] = process.pid
    try:
        _poll_ready(args, record, process)
        _pass(record, "A", "profile command", "health/live", "health/ready")
        _pass(record, "B", "SystemContainer-backed readiness")

        _http(
            args,
            record,
            "GET",
            "/agenda",
            expected=(401,),
        )
        _http(
            args,
            record,
            "GET",
            "/agenda",
            token="wrong-token",
            expected=(401,),
        )
        _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )

        _, task = _http(
            args,
            record,
            "POST",
            "/tasks",
            token=token,
            headers=workspace_headers,
            body={
                "title": "ACC-020 UserTask",
                "due_at": (now - timedelta(hours=1)).isoformat(),
            },
            expected=(201,),
        )
        _, reminder = _http(
            args,
            record,
            "POST",
            f"/tasks/{task['id']}/reminders",
            token=token,
            headers=workspace_headers,
            body={
                "remind_at": (now + timedelta(seconds=2)).isoformat(),
                "timezone": "UTC",
            },
            expected=(201,),
        )
        _, inbox = _http(
            args,
            record,
            "POST",
            "/inbox",
            token=token,
            headers=workspace_headers,
            body={"content": "ACC-020 Inbox"},
            expected=(201,),
        )
        _, waiting = _http(
            args,
            record,
            "POST",
            "/waiting-for",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 Waiting-For",
                "waiting_on": "Owner",
                "next_review_at": (now - timedelta(minutes=1)).isoformat(),
                "timezone": "UTC",
            },
            expected=(201,),
        )
        _, work_log = _http(
            args,
            record,
            "POST",
            "/work-logs",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 Work Log",
                "raw_text": "Executable rehearsal evidence",
                "occurred_at": now.isoformat(),
                "timezone": "UTC",
            },
            expected=(200,),
        )
        canonical_ids = [
            task["id"],
            reminder["id"],
            inbox["id"],
            waiting["item"]["id"],
            work_log["id"],
        ]
        record["canonical_ids"] = canonical_ids
        _pass(record, "C", *canonical_ids)

        idempotency_key = "acc020-reminder-reschedule"
        _, reminder_status = _http(
            args,
            record,
            "PATCH",
            f"/reminders/{reminder['id']}",
            token=token,
            headers={
                **workspace_headers,
                "Idempotency-Key": idempotency_key,
            },
            body={
                "scheduled_for": (now + timedelta(seconds=2)).isoformat(),
                "timezone": "UTC",
                "revision": reminder["revision"],
            },
        )
        record["idempotency_keys"].append(idempotency_key)
        record["mutations"].append({
            "domain": "reminder",
            "id": reminder["id"],
            "status": reminder_status["status"],
        })

        for _ in range(30):
            time.sleep(0.15)
            _, reminder_status = _http(
                args,
                record,
                "GET",
                f"/reminders/{reminder['id']}/status",
                token=token,
                headers=workspace_headers,
            )
            if reminder_status["status"] == "triggered":
                break
        if reminder_status is None or reminder_status["status"] != "triggered":
            raise ProductAcceptanceError(
                "one-shot Reminder did not reach triggered"
            )

        _, agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _pass(record, "D", f"agenda keys={sorted(agenda)}")
        _, today = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            "/daily-review?date=yesterday",
            token=token,
            headers=workspace_headers,
        )
        _pass(record, "E", f"today total={today['page']['total_count']}")
        _, hints = _http(
            args,
            record,
            "GET",
            "/daily-review/action-hints?date=today",
            token=token,
            headers=workspace_headers,
        )
        _pass(record, "F", f"hint count={len(hints)}")

        _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={},
            expected=(400,),
        )
        _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={"expected_revision": task["revision"] + 5},
            expected=(409,),
        )
        _, completed = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={"expected_revision": task["revision"]},
        )
        record["mutations"].append({
            "domain": "user_task",
            "id": completed["id"],
            "status": completed["status"],
        })
        record["revisions"].append({
            "id": task["id"],
            "before": task["revision"],
            "after": completed["revision"],
        })
        _pass(record, "G", f"revision={completed['revision']}")

        _, followed = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/follow-ups",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": waiting["item"]["revision"],
                "note": "ACC-020 follow-up",
            },
        )
        _pass(record, "H", f"revision={followed['item']['revision']}")
        _, resolved_inbox = _http(
            args,
            record,
            "POST",
            f"/inbox/{inbox['id']}/resolve/note",
            token=token,
            headers=workspace_headers,
        )
        record["claims_and_sagas"].append({
            "inbox_id": inbox["id"],
            "resolved_type": resolved_inbox["resolved_type"],
        })
        _pass(record, "I", "InboxResolutionClaim completed")
        _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _pass(record, "J", "review refreshed after mutations")

        _http(
            args,
            record,
            "GET",
            f"/tasks/{task['id']}",
            token=token,
            headers={**workspace_headers, "X-Workspace-ID": "isolated"},
            expected=(404,),
        )
        _pass(record, "K", "cross-workspace read returned 404")
        _pass(record, "M", "missing and stale revision failed before mutation")
        _pass(record, "N", "read and hint paths completed without mutation API")

        for _ in range(4):
            time.sleep(0.15)
            _, health = _http(args, record, "GET", "/health")
            record["health_snapshots"].append(health)
            record["connection_counts"].append(
                health["database_connections"]
            )
        _pass(
            record,
            "O",
            "multiple scheduler ticks and idle health snapshots",
            "one-shot Reminder triggered",
        )
        _write_manifest(manifest_path, record)
    finally:
        exit_code = _stop_api(process, stdout, stderr)
    _assert_graceful_shutdown(
        exit_code=exit_code,
        stderr_path=evidence / "source-api-stderr.log",
        label="source",
    )
    record["connection_counts"].append(0)
    _pass(record, "P", "graceful shutdown", "connection_count=0")
    _pass(record, "Q", "process cleanup completed")

    restarted, restart_stdout, restart_stderr = _start_api(
        args,
        env=env,
        label="source-restart-api",
        evidence=evidence,
        record=record,
    )
    record["restart_api_pid"] = restarted.pid
    try:
        _poll_ready(args, record, restarted)
        _, restarted_task = _http(
            args,
            record,
            "GET",
            f"/tasks/{task['id']}",
            token=token,
            headers=workspace_headers,
        )
        if (
            restarted_task["revision"] != completed["revision"]
            or restarted_task["status"] != completed["status"]
        ):
            raise ProductAcceptanceError("same-root restart changed UserTask")
        _http(
            args,
            record,
            "GET",
            f"/reminders/{reminder['id']}/status",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}/events",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            f"/inbox/{inbox['id']}",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            f"/work-logs/{work_log['id']}",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
    finally:
        restart_exit = _stop_api(
            restarted,
            restart_stdout,
            restart_stderr,
        )
    _assert_graceful_shutdown(
        exit_code=restart_exit,
        stderr_path=evidence / "source-restart-api-stderr.log",
        label="source restart",
    )
    _pass(record, "R", "new process recovered source root")

    before = file_manifest(source)
    record["source_manifest_before_restore"] = before
    restore.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, restore, dirs_exist_ok=True)
    record["restore_manifest"] = file_manifest(restore)
    _pass(record, "S", f"source files={len(before)}")
    _pass(record, "T", f"restore files={len(record['restore_manifest'])}")

    restore_env = _runtime_env(
        args,
        data_root=restore,
        spy_root=spy_root,
        counter=counter,
    )
    restored, restored_stdout, restored_stderr = _start_api(
        args,
        env=restore_env,
        label="restore-api",
        evidence=evidence,
        record=record,
    )
    record["restore_api_pid"] = restored.pid
    try:
        _poll_ready(args, record, restored)
        _, restored_task = _http(
            args,
            record,
            "GET",
            f"/tasks/{task['id']}",
            token=token,
            headers=workspace_headers,
        )
        if (
            restored_task["revision"] != completed["revision"]
            or restored_task["status"] != completed["status"]
        ):
            raise ProductAcceptanceError("restored UserTask differs")
        _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, appended = _http(
            args,
            record,
            "POST",
            "/work-logs",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 restore append",
                "raw_text": "write after isolated restore",
                "occurred_at": datetime.now(UTC).isoformat(),
                "timezone": "UTC",
            },
            expected=(200,),
        )
        record["canonical_ids"].append(appended["id"])
        _pass(record, "U", "objects/revisions/agenda/review restored")
        _pass(record, "V", "FailureInfo/revision/Saga evidence recorded")
    finally:
        restored_exit = _stop_api(
            restored,
            restored_stdout,
            restored_stderr,
        )
    _assert_graceful_shutdown(
        exit_code=restored_exit,
        stderr_path=evidence / "restore-api-stderr.log",
        label="restore",
    )

    after = file_manifest(source)
    record["source_manifest_after_restore"] = after
    if before != after:
        raise ProductAcceptanceError(
            "source data changed during isolated restore verification"
        )
    calls = len(counter.read_text(encoding="utf-8").splitlines())
    record["provider_spy_call_count"] = calls
    events_path = spy_root / "events.log"
    scheduler_path = spy_root / "scheduler.log"
    record["event_bus"] = (
        events_path.read_text(encoding="utf-8").splitlines()
        if events_path.exists()
        else []
    )
    record["scheduler_mutations"] = (
        scheduler_path.read_text(encoding="utf-8").splitlines()
        if scheduler_path.exists()
        else []
    )
    if calls != 0:
        raise ProductAcceptanceError(f"provider spy recorded {calls} calls")
    _pass(record, "L", "provider spy call count=0")
    if any(
        item["result"] != "PASS"
        for item in record["scenarios"].values()
    ):
        raise ProductAcceptanceError("one or more A-V scenarios did not pass")
    record["status"] = (
        "REHEARSAL_COMPLETE_NOT_FORMAL_ACCEPTANCE"
        if args.rehearsal
        else "FORMAL_ACCEPTANCE_COMPLETE"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-head", required=True)
    parser.add_argument("--expected-driver-sha256", required=True)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument("--source-data-root", type=Path, required=True)
    parser.add_argument("--restore-data-root", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--rehearsal", action="store_true")
    modes.add_argument("--formal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    driver = Path(__file__).resolve()
    manifest_path = args.evidence_dir.resolve() / "manifest.json"
    try:
        validated = validate_harness(args, driver)
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        record = _base_manifest(args, validated)
        _write_manifest(manifest_path, record)
        if not args.prepare_only:
            _execute(args, record, manifest_path)
        _write_manifest(manifest_path, record)
        print(manifest_path)
        return 0
    except HarnessError as exc:
        print(f"{HARNESS_FAILURE}: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - acceptance boundary
        if manifest_path.parent.exists():
            try:
                current = (
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest_path.exists()
                    else {}
                )
                current.update({
                    "status": PRODUCT_FAILURE,
                    "failure_type": type(exc).__name__,
                    "failure": str(exc),
                })
                _write_manifest(manifest_path, current)
            except Exception:  # noqa: BLE001, S110 - preserve primary failure
                pass
        print(f"{PRODUCT_FAILURE}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
