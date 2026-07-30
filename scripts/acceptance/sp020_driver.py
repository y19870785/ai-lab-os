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
import sqlite3
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
SCENARIO_REQUIRED_CHECKS = {
    "A": {
        "invalid timezone",
        "invalid provider",
        "missing auth token",
        "relative data root",
        "relative sqlite root",
        "sqlite outside data root",
        "unknown profile",
        "no checkout data fallback",
    },
    "B": {
        "health live",
        "health ready",
        "lifecycle ready",
        "accepting work",
        "provider mode",
        "component health",
        "auth rejection",
        "single uvicorn container pid",
    },
    "C": {
        "canonical prefixes",
        "revisions recorded",
        "workspace recorded",
        "sqlite rows recorded",
        "five domains created",
        "canonical ids persisted",
    },
    "D": {
        "agenda contains real objects",
        "canonical ids match",
        "stable ordering",
        "repeat result deterministic",
        "complete workspace",
        "read side effects unchanged",
    },
    "E": {
        "api today",
        "api yesterday",
        "cli today json",
        "cli yesterday json",
        "date and timezone match",
        "period and source status match",
        "canonical sections and pagination match",
        "only volatile instants differ",
    },
    "F": {
        "repeated hints identical",
        "fields complete",
        "required arguments callable",
        "reminder idempotency optional",
        "six inbox actions",
        "unsupported tuple empty",
        "hint side effects unchanged",
    },
    "G": {
        "update stale",
        "legacy complete compatibility",
        "legacy cancel compatibility",
        "review missing revision",
        "active stale revision",
        "terminal stale revision",
        "terminal exact revision",
        "cross workspace mutation",
        "public task response",
        "sqlite revision status",
    },
    "H": {
        "follow up",
        "resolve",
        "snooze",
        "cancel",
        "reopen",
        "history event",
        "revision progression",
        "stale revision",
        "unsupported state",
        "missing argument no write",
    },
    "I": {
        "target resolution",
        "note or dismiss",
        "missing waiting confirmation",
        "resolution replay",
        "competing resolution",
        "durable claim",
        "target id",
        "source resolved",
        "single target",
    },
    "J": {
        "terminal task reclassified",
        "waiting history reflected",
        "pending inbox removed",
        "no duplicates",
        "no omissions",
        "no snapshot or automatic mutation",
    },
    "K": {
        "task invisible",
        "mutation blocked",
        "agenda invisible",
        "review invisible",
        "hint invisible",
        "cli invisible",
        "ceo invisible",
        "no default fallback",
    },
    "L": {
        "provider spy installed",
        "provider calls zero",
    },
    "M": {
        "missing canonical id unchanged",
        "missing revision unchanged",
        "stale revision unchanged",
        "invalid status reason unchanged",
        "unsupported work log mutation unchanged",
        "waiting confirmation unchanged",
        "required arguments unchanged",
        "event scheduler revision unchanged",
    },
    "N": {
        "read hint emit no mutation event",
        "mutations emit existing events",
        "event workspace trace persisted",
        "publish after stop fails closed",
    },
    "O": {
        "multiple ticks",
        "one shot job",
        "job status revision",
        "run status",
        "claim token expiry",
        "occurrence",
        "reminder reconciliation",
        "effectively once",
        "idle window",
        "health and background tasks",
        "real connection count",
    },
    "P": {
        "ready draining terminal",
        "draining rejects work",
        "background tasks converge",
        "scheduler services bus stop",
        "database closes last",
        "connection count zero observed",
        "shutdown failures recorded",
        "graceful process exit",
    },
    "Q": {
        "external repeated shutdown",
        "double scheduler shutdown",
        "partial startup failure",
        "rollback order",
        "event bus stopped",
        "tasks cleaned",
        "connections zero",
        "failed container cannot restart",
        "no duplicate execution",
    },
    "R": {
        "user task restart",
        "reminder restart",
        "scheduler job run restart",
        "claim occurrence restart",
        "inbox saga restart",
        "waiting history restart",
        "work log restart",
        "agenda restart",
        "today review restart",
        "yesterday review restart",
    },
    "S": {
        "shutdown gates passed before copy",
        "complete file inventory",
        "size and sha256",
        "no product process during copy",
    },
    "T": {
        "independent absolute profile",
        "source root not accessed",
        "checkout data not accessed",
        "source hashes unchanged",
    },
    "U": {
        "canonical ids equal",
        "revision status equal",
        "history equal",
        "jobs runs equal",
        "claims saga equal",
        "agenda equal",
        "today review equal",
        "yesterday review equal",
        "restore append leaves source unchanged",
    },
    "V": {
        "config failure info",
        "auth failure info",
        "workspace failure info",
        "date query failure info",
        "not found failure info",
        "stale revision failure info",
        "unsupported state failure info",
        "dependency scheduler failure info",
        "shutdown restore failure info",
        "failure fields secret safe",
        "idempotency and saga replay",
    },
}
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


def _safe(value: Any, *, secret: str = "") -> Any:
    """Return JSON-safe evidence with obvious secret-bearing fields redacted."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(marker in str(key).lower() for marker in (
                    "token",
                    "authorization",
                    "api_key",
                    "secret",
                ))
                else _safe(item, secret=secret)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe(item, secret=secret) for item in value]
    text = str(value)
    if secret and secret in text:
        return text.replace(secret, "[REDACTED]")
    return value


def _write_json(path: Path, value: Any, *, secret: str = "") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(value, secret=secret), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path.name


def sqlite_snapshot(data_root: Path) -> dict[str, Any]:
    """Capture deterministic table rows from every SQLite file."""

    snapshot: dict[str, Any] = {}
    candidates = sorted({
        path
        for pattern in ("*.db", "*.sqlite", "*.sqlite3")
        for path in data_root.rglob(pattern)
        if path.is_file()
    })
    for path in candidates:
        relative = path.relative_to(data_root).as_posix()
        database: dict[str, Any] = {"tables": {}}
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            ]
            for table in tables:
                quoted = table.replace('"', '""')
                rows = [
                    {key: row[key] for key in row.keys()}  # noqa: SIM118
                    for row in connection.execute(
                        f'SELECT * FROM "{quoted}" ORDER BY rowid'
                    )
                ]
                database["tables"][table] = rows
        snapshot[relative] = database
    return snapshot


def _check(
    name: str,
    *,
    expected: Any,
    actual: Any,
    evidence_path: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "expected": _safe(expected),
        "actual": _safe(actual),
        "passed": actual == expected,
        "evidence_path": evidence_path,
    }


def _record_scenario(
    record: dict[str, Any],
    scenario: str,
    *,
    started_at: str,
    entrypoints: list[str],
    checks: list[dict[str, Any]],
    facts: dict[str, Any],
    evidence_dir: Path,
) -> None:
    """A scenario can pass only through complete structured assertions."""

    required = SCENARIO_REQUIRED_CHECKS[scenario]
    names = {item.get("name") for item in checks}
    missing = sorted(required - names)
    if missing:
        raise ProductAcceptanceError(
            f"scenario {scenario} is missing required checks: {missing}"
        )
    malformed = [
        item.get("name", "<unnamed>")
        for item in checks
        if set(item) != {
            "name",
            "expected",
            "actual",
            "passed",
            "evidence_path",
        }
        or not item.get("evidence_path")
    ]
    if malformed:
        raise ProductAcceptanceError(
            f"scenario {scenario} has malformed checks: {malformed}"
        )
    required_facts = {
        "exit_codes",
        "http_statuses",
        "response_facts",
        "object_ids",
        "workspace",
        "revision_status",
        "database_evidence",
        "spy_evidence",
    }
    missing_facts = sorted(required_facts - set(facts))
    if missing_facts:
        raise ProductAcceptanceError(
            f"scenario {scenario} is missing facts: {missing_facts}"
        )
    result = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    scenario_record = {
        "result": result,
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "entrypoints": entrypoints,
        **_safe(facts),
        "checks": checks,
    }
    scenario_path = evidence_dir / f"scenario-{scenario}.json"
    _write_json(scenario_path, scenario_record)
    scenario_record["evidence_paths"] = sorted({
        scenario_path.name,
        *(str(item["evidence_path"]) for item in checks),
    })
    record["scenarios"][scenario] = scenario_record
    if result != "PASS":
        failures = [
            {
                "name": item["name"],
                "expected": item["expected"],
                "actual": item["actual"],
            }
            for item in checks
            if not item["passed"]
        ]
        raise ProductAcceptanceError(
            f"scenario {scenario} failed checks: {failures}"
        )


def _finish_scenario(
    record: dict[str, Any],
    scenario: str,
    *,
    started_at: str,
    entrypoints: list[str],
    actuals: dict[str, Any],
    evidence_payload: dict[str, Any],
    evidence_dir: Path,
    secret: str,
    facts: dict[str, Any],
) -> None:
    """Persist raw scenario evidence before evaluating its named checks."""

    evidence_path = evidence_dir / f"scenario-{scenario}-evidence.json"
    _write_json(evidence_path, evidence_payload, secret=secret)
    required = SCENARIO_REQUIRED_CHECKS[scenario]
    missing = sorted(required - set(actuals))
    if missing:
        raise ProductAcceptanceError(
            f"scenario {scenario} has no actuals for checks: {missing}"
        )
    checks = [
        _check(
            name,
            expected=True,
            actual=bool(actuals[name]),
            evidence_path=evidence_path.name,
        )
        for name in sorted(required)
    ]
    _record_scenario(
        record,
        scenario,
        started_at=started_at,
        entrypoints=entrypoints,
        checks=checks,
        facts=facts,
        evidence_dir=evidence_dir,
    )


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


def capture_command(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    records: list[dict[str, object]],
    evidence: Path,
    label: str,
    expected_codes: tuple[int, ...],
    input_text: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run an assertion command and persist its real stdout/stderr."""

    started = datetime.now(UTC)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    stdout_path = evidence / f"{label}-stdout.log"
    stderr_path = evidence / f"{label}-stderr.log"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    item = {
        "command": command,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "exit_code": result.returncode,
        "stdout_path": stdout_path.name,
        "stderr_path": stderr_path.name,
    }
    records.append(item)
    if result.returncode not in expected_codes:
        raise ProductAcceptanceError(
            f"{label} exited with {result.returncode}, expected {expected_codes}"
        )
    return {
        **item,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _evidence_snapshot(
    *,
    data_root: Path,
    evidence: Path,
    label: str,
    secret: str,
) -> dict[str, Any]:
    snapshot = {
        "files": file_manifest(data_root),
        "sqlite": sqlite_snapshot(data_root),
    }
    path = evidence / f"{label}.json"
    _write_json(path, snapshot, secret=secret)
    return {"path": path.name, "value": snapshot}


def _normalized_review(review: dict[str, Any]) -> dict[str, Any]:
    return _without_volatile(review)


def _without_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_volatile(item)
            for key, item in value.items()
            if key not in {"generated_at", "as_of", "trace_id"}
        }
    if isinstance(value, list):
        return [_without_volatile(item) for item in value]
    return value


def _review_ids(review: dict[str, Any]) -> list[str]:
    sections = (
        "blocked",
        "follow_ups",
        "in_progress",
        "completed",
        "informational",
        "pending_inbox",
    )
    return [
        item["source_id"]
        for section in sections
        for item in review.get(section, {}).get("items", [])
    ]


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
        "sqlite_evidence": [],
        "shutdown_observations": [],
        "partial_start_probe": {},
        "source_restore_comparison": {},
        "failure_info_checks": [],
        "scenarios": {
            scenario: {
                "result": "NOT_MEASURED" if prepare else "PENDING",
                "started_at": None,
                "ended_at": None,
                "entrypoints": [],
                "exit_codes": [],
                "http_statuses": [],
                "response_facts": {},
                "object_ids": [],
                "workspace": {},
                "revision_status": [],
                "database_evidence": [],
                "spy_evidence": [],
                "checks": [],
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
        """import json
import os
from datetime import UTC, datetime
from pathlib import Path
from core.providers.llm.mock import MockLLMProvider
from core.providers.llm.openai import OpenAILLMProvider
from core.bus.bus import MemoryBus
from core.scheduler.runtime import SchedulerRuntime
from core.system.container import SystemContainer
from core.database.manager import DatabaseManager
from core.inbox.service import InboxService
from core.reminders.service import ReminderService
from core.user_tasks.service import UserTaskService
from core.waiting_for.service import WaitingForService
from core.work_log.service import WorkLogService
_counter = Path(os.environ["ACC020_PROVIDER_SPY_FILE"])
_root = Path(os.environ["ACC020_SPY_ROOT"])
_counter.with_name("installed").write_text("installed", encoding="utf-8")
_events = _counter.with_name("events.log")
_scheduler = _counter.with_name("scheduler.log")
_shutdown = _counter.with_name("shutdown.log")
_configured_workspace = {
    "tenant_id": os.environ.get("AI_LAB_TENANT_ID", ""),
    "workspace_id": os.environ.get("AI_LAB_WORKSPACE_ID", ""),
    "namespace": os.environ.get("AI_LAB_NAMESPACE", ""),
    "session_id": os.environ.get("AI_LAB_SESSION_ID", ""),
    "agent_id": os.environ.get("AI_LAB_AGENT_ID", ""),
}
def _safe(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(marker in str(key).lower() for marker in (
                    "token", "authorization", "api_key", "secret"
                ))
                else _safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
def _append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_safe(value), ensure_ascii=False) + "\\n")
def _stamp(kind, **facts):
    _append(_shutdown, {
        "event": kind,
        "pid": os.getpid(),
        "timestamp": datetime.now(UTC).isoformat(),
        **facts,
    })
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
    serialized = _safe(event)
    payload = serialized.get("payload", {}) if isinstance(serialized, dict) else {}
    metadata = serialized.get("metadata", {}) if isinstance(serialized, dict) else {}
    workspace = (
        payload.get("workspace_key", {})
        if isinstance(payload, dict)
        else {}
    ) or _configured_workspace
    _append(_events, {
        "topic": topic,
        "event_type": (
            serialized.get("event_type", event.__class__.__name__)
            if isinstance(serialized, dict)
            else event.__class__.__name__
        ),
        "payload": payload,
        "workspace": workspace,
        "trace_id": (
            metadata.get("trace_id", "")
            or payload.get("trace_id", "")
            or workspace.get("trace_id", "")
        ),
        "timestamp": datetime.now(UTC).isoformat(),
    })
    return await _publish(self, topic, event)
MemoryBus.publish = _record_publish
_schedule = SchedulerRuntime.schedule
async def _record_schedule(self, request):
    _append(_scheduler, {
        "operation": "schedule",
        "request": _safe(request),
        "timestamp": datetime.now(UTC).isoformat(),
    })
    return await _schedule(self, request)
SchedulerRuntime.schedule = _record_schedule
_scheduler_shutdown = SchedulerRuntime.shutdown
async def _record_scheduler_shutdown(self):
    _stamp("scheduler_shutdown_before")
    try:
        return await _scheduler_shutdown(self)
    finally:
        _stamp("scheduler_shutdown_after")
SchedulerRuntime.shutdown = _record_scheduler_shutdown
_bus_stop = MemoryBus.stop
async def _record_bus_stop(self):
    _stamp("event_bus_stop_before", running=self.is_running)
    try:
        return await _bus_stop(self)
    finally:
        _stamp("event_bus_stop_after", running=self.is_running)
MemoryBus.stop = _record_bus_stop
_database_close = DatabaseManager.close_all
async def _record_database_close(self):
    _stamp("database_close_before", connections=self.connection_count)
    try:
        result = _database_close(self)
        if hasattr(result, "__await__"):
            return await result
        return result
    finally:
        _stamp("database_close_after", connections=self.connection_count)
DatabaseManager.close_all = _record_database_close
_container_shutdown = SystemContainer.shutdown
async def _record_container_shutdown(self):
    before = await self.health()
    _stamp(
        "container_shutdown_before",
        lifecycle=before.get("lifecycle"),
        accepting_work=before.get("accepting_work"),
        background_tasks=before.get("background_tasks"),
        database_connections=before.get("database_connections"),
    )
    try:
        return await _container_shutdown(self)
    finally:
        after = await self.health()
        _stamp(
            "container_shutdown_after",
            lifecycle=after.get("lifecycle"),
            accepting_work=after.get("accepting_work"),
            background_tasks=after.get("background_tasks"),
            database_connections=after.get("database_connections"),
            shutdown_failures=after.get("shutdown_failures"),
        )
SystemContainer.shutdown = _record_container_shutdown
def _wrap_service_close(service_type, name):
    original = service_type.close
    async def recorded(self):
        _stamp("service_close_before", service=name)
        try:
            return await original(self)
        finally:
            _stamp("service_close_after", service=name)
    service_type.close = recorded
for _service_type, _service_name in (
    (ReminderService, "reminder"),
    (WaitingForService, "waiting_for"),
    (InboxService, "inbox"),
    (WorkLogService, "work_log"),
    (UserTaskService, "user_task"),
):
    _wrap_service_close(_service_type, _service_name)
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
        "ACC020_SPY_ROOT": str(spy_root),
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
    started_at = datetime.now(UTC).isoformat()
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
    trace_id = request_headers["X-Trace-ID"]
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
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "trace_id": trace_id,
        "workspace": {
            key: value
            for key, value in request_headers.items()
            if key.startswith("X-") and key != "X-Trace-ID"
        },
        "request_facts": _safe(body or {}),
        "response_facts": _safe(parsed),
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


def _scenario_facts(
    record: dict[str, Any],
    *,
    http_start: int,
    command_start: int,
    response_facts: dict[str, Any],
    object_ids: list[str],
    workspace: dict[str, Any],
    revision_status: list[dict[str, Any]],
    database_evidence: list[str],
    spy_evidence: list[str],
) -> dict[str, Any]:
    operations = record["http_operations"][http_start:]
    commands = record["commands"][command_start:]
    return {
        "exit_codes": [
            item.get("exit_code")
            for item in commands
            if "exit_code" in item
        ],
        "http_statuses": [
            {
                "method": item["method"],
                "path": item["path"],
                "status": item["status"],
            }
            for item in operations
        ],
        "response_facts": _safe(response_facts),
        "object_ids": object_ids,
        "workspace": workspace,
        "revision_status": revision_status,
        "database_evidence": database_evidence,
        "spy_evidence": spy_evidence,
    }


def _partial_start_probe(
    *,
    repo: Path,
    env: dict[str, str],
    evidence: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    script = evidence / "partial-start-probe.py"
    output = evidence / "partial-start-probe.json"
    script.write_text(
        """import asyncio
import json
import sys
from pathlib import Path
from types import MethodType
from core.system import create_system, load_system_settings

async def main():
    output = Path(sys.argv[1])
    failed = await create_system(load_system_settings(load_dotenv=False))
    original = failed.waiting_for_service.initialize
    async def injected(self):
        raise RuntimeError("acc020 injected partial-start failure")
    failed.waiting_for_service.initialize = MethodType(
        injected, failed.waiting_for_service
    )
    start_error = ""
    try:
        await failed.start()
    except Exception as exc:
        start_error = type(exc).__name__ + ": " + str(exc)
    failed.waiting_for_service.initialize = original
    failed_health = await failed.health()
    restart_error = ""
    try:
        await failed.start()
    except Exception as exc:
        restart_error = type(exc).__name__ + ": " + str(exc)
    await failed.shutdown()
    await failed.shutdown()
    failed_final = await failed.health()

    healthy_root = output.parent / "q-healthy-data"
    import os
    os.environ["AI_LAB_DATA_DIR"] = str(healthy_root)
    os.environ["AI_LAB_SQLITE_DIR"] = str(healthy_root / "sqlite")
    healthy = await create_system(load_system_settings(load_dotenv=False))
    await healthy.start()
    if healthy.scheduler_runtime is not None:
        await healthy.scheduler_runtime.shutdown()
        await healthy.scheduler_runtime.shutdown()
    release_close = asyncio.Event()
    original_close = healthy.waiting_for_service.close
    async def delayed_close(self):
        await release_close.wait()
        return await original_close()
    healthy.waiting_for_service.close = MethodType(
        delayed_close, healthy.waiting_for_service
    )
    shutdown_task = asyncio.create_task(healthy.shutdown())
    while healthy._lifecycle.state.value != "draining":
        await asyncio.sleep(0)
    draining_lifecycle = healthy._lifecycle.state.value
    draining_error = ""
    try:
        with healthy.work_admission_gate.admit():
            pass
    except Exception as exc:
        draining_error = type(exc).__name__ + ": " + str(exc)
    release_close.set()
    await shutdown_task
    await healthy.shutdown()
    healthy_final = await healthy.health()
    publish_after_stop_error = ""
    try:
        await healthy.event_bus.publish("acc020.after-stop", object())
    except Exception as exc:
        publish_after_stop_error = type(exc).__name__ + ": " + str(exc)
    result = {
        "start_error": start_error,
        "restart_error": restart_error,
        "failed_health": failed_health,
        "failed_final": failed_final,
        "healthy_final": healthy_final,
        "event_bus_stopped": not failed.event_bus.is_running,
        "failed_tasks_clean": failed_health["background_tasks"] == 0,
        "healthy_tasks_clean": healthy_final["background_tasks"] == 0,
        "failed_connections": failed_final["database_connections"],
        "healthy_connections": healthy_final["database_connections"],
        "failed_lifecycle": failed_final["lifecycle"],
        "healthy_lifecycle": healthy_final["lifecycle"],
        "double_shutdown_completed": True,
        "double_scheduler_shutdown_completed": True,
        "draining_lifecycle": draining_lifecycle,
        "draining_error": draining_error,
        "publish_after_stop_error": publish_after_stop_error,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

asyncio.run(main())
""",
        encoding="utf-8",
    )
    probe_env = dict(env)
    probe_root = evidence / "q-failed-data"
    probe_env["AI_LAB_DATA_DIR"] = str(probe_root)
    probe_env["AI_LAB_SQLITE_DIR"] = str(probe_root / "sqlite")
    capture_command(
        [sys.executable, str(script), str(output)],
        env=probe_env,
        cwd=repo,
        records=record["commands"],
        evidence=evidence,
        label="partial-start-probe",
        expected_codes=(0,),
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _failure_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("detail"), dict):
        return value["detail"]
    return value if isinstance(value, dict) else {}


def _failure_is_complete(value: Any, *, secret: str) -> bool:
    failure = _failure_payload(value)
    required = {
        "code",
        "category",
        "component",
        "operation",
        "trace_id",
        "retryable",
        "details",
    }
    serialized = json.dumps(_safe(failure, secret=secret), ensure_ascii=False)
    return (
        required <= set(failure)
        and isinstance(failure.get("retryable"), bool)
        and bool(failure.get("trace_id"))
        and secret not in serialized
    )


def _execute(
    args: argparse.Namespace,
    record: dict[str, Any],
    manifest_path: Path,
) -> None:
    repo = args.repository_root.resolve()
    repository_path = str(repo)
    if repository_path not in sys.path:
        sys.path.insert(0, repository_path)
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
    a_started = datetime.now(UTC).isoformat()
    a_command_start = len(record["commands"])
    checkout_data_before = file_manifest(repo / "data")
    negative_profiles: dict[str, dict[str, Any]] = {}
    negative_cases = {
        "invalid timezone": {"AI_LAB_TIMEZONE": "Mars/Olympus"},
        "invalid provider": {"AI_LAB_PROVIDER_MODE": "invalid"},
        "missing auth token": {"AI_LAB_API_TOKEN": None},
        "relative data root": {"AI_LAB_DATA_DIR": "relative-data"},
        "relative sqlite root": {"AI_LAB_SQLITE_DIR": "relative-sqlite"},
        "sqlite outside data root": {
            "AI_LAB_SQLITE_DIR": str(evidence / "outside-sqlite"),
        },
        "unknown profile": {"AI_LAB_PROFILE": "local_daily"},
    }
    for index, (name, overrides) in enumerate(negative_cases.items(), start=1):
        invalid_env = dict(env)
        for key, value in overrides.items():
            if value is None:
                invalid_env.pop(key, None)
            else:
                invalid_env[key] = value
        result = capture_command(
            [
                sys.executable,
                "-m",
                "cli",
                "profile",
                "--require-local-daily",
            ],
            env=invalid_env,
            cwd=repo,
            records=record["commands"],
            evidence=evidence,
            label=f"profile-negative-{index}",
            expected_codes=(1, 2),
        )
        negative_profiles[name] = {
            "exit_code": result["exit_code"],
            "stderr_path": result["stderr_path"],
        }
    run_command(
        [sys.executable, "-m", "cli", "profile", "--require-local-daily"],
        env=env,
        cwd=repo,
        records=record["commands"],
    )
    if not (spy_root / "installed").exists():
        raise HarnessError("Provider spy was not installed")
    a_evidence = {
        "negative_profiles": negative_profiles,
        "checkout_data_before": checkout_data_before,
        "checkout_data_after": file_manifest(repo / "data"),
    }
    _finish_scenario(
        record,
        "A",
        started_at=a_started,
        entrypoints=["subprocess:python -m cli profile --require-local-daily"],
        actuals={
            **{
                name: value["exit_code"] != 0
                for name, value in negative_profiles.items()
            },
            "no checkout data fallback": (
                checkout_data_before == file_manifest(repo / "data")
            ),
        },
        evidence_payload=a_evidence,
        evidence_dir=evidence,
        secret=token,
        facts=_scenario_facts(
            record,
            http_start=len(record["http_operations"]),
            command_start=a_command_start,
            response_facts=negative_profiles,
            object_ids=[],
            workspace=record["workspace"],
            revision_status=[],
            database_evidence=[],
            spy_evidence=[result["stderr_path"] for result in negative_profiles.values()],
        ),
    )
    process, stdout, stderr = _start_api(
        args,
        env=env,
        label="source-api",
        evidence=evidence,
        record=record,
    )
    record["api_pid"] = process.pid
    try:
        b_started = datetime.now(UTC).isoformat()
        b_http_start = len(record["http_operations"])
        b_command_start = len(record["commands"])
        _poll_ready(args, record, process)
        _, live = _http(args, record, "GET", "/health/live")
        _, ready = _http(args, record, "GET", "/health/ready")
        _, health = _http(args, record, "GET", "/health")
        missing_auth_status, missing_auth = _http(
            args,
            record,
            "GET",
            "/agenda",
            expected=(401,),
        )
        wrong_auth_status, wrong_auth = _http(
            args,
            record,
            "GET",
            "/agenda",
            token="wrong-token",
            expected=(401,),
        )
        authorized_status, authorized_agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        time.sleep(0.1)
        source_log = evidence / "source-api-stderr.log"
        source_log_text = source_log.read_text(
            encoding="utf-8", errors="replace"
        )
        import re
        uvicorn_pids = re.findall(
            r"Started server process \[(\d+)\]",
            source_log_text,
        )
        b_evidence = {
            "live": live,
            "ready": ready,
            "health": health,
            "missing_auth": missing_auth,
            "wrong_auth": wrong_auth,
            "authorized_agenda": authorized_agenda,
            "launcher_pid": process.pid,
            "uvicorn_pids": uvicorn_pids,
        }
        components = health.get("components", {})
        _finish_scenario(
            record,
            "B",
            started_at=b_started,
            entrypoints=[
                "GET /health/live",
                "GET /health/ready",
                "GET /health",
                "GET /agenda",
            ],
            actuals={
                "health live": live.get("status") in {"alive", "ok", "healthy"},
                "health ready": ready.get("status") in {"ready", "ok", "healthy"},
                "lifecycle ready": health.get("lifecycle") == "ready",
                "accepting work": health.get("accepting_work") is True,
                "provider mode": health.get("provider_mode") == "mock",
                "component health": (
                    bool(components)
                    and all(
                        item.get("status") not in {"failed", "error"}
                        for item in components.values()
                        if isinstance(item, dict)
                    )
                ),
                "auth rejection": (
                    missing_auth_status == wrong_auth_status == 401
                    and authorized_status == 200
                ),
                "single uvicorn container pid": len(set(uvicorn_pids)) == 1,
            },
            evidence_payload=b_evidence,
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=b_http_start,
                command_start=b_command_start,
                response_facts=b_evidence,
                object_ids=[],
                workspace=record["workspace"],
                revision_status=[],
                database_evidence=[],
                spy_evidence=["source-api-stderr.log"],
            ),
        )

        c_started = datetime.now(UTC).isoformat()
        c_http_start = len(record["http_operations"])
        c_command_start = len(record["commands"])
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
                "remind_at": (now + timedelta(minutes=30)).isoformat(),
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
        c_snapshot = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="c-created-sqlite",
            secret=token,
        )
        c_serialized = json.dumps(c_snapshot["value"], ensure_ascii=False)
        response_revisions = [
            {"id": task["id"], "revision": task["revision"]},
            {"id": reminder["id"], "revision": reminder["revision"]},
            {
                "id": waiting["item"]["id"],
                "revision": waiting["item"]["revision"],
            },
        ]
        prefix_pairs = (
            (task["id"], "ut_"),
            (reminder["id"], "rem_"),
            (inbox["id"], "inbox_"),
            (waiting["item"]["id"], "wf_"),
            (work_log["id"], "wl_"),
        )
        _finish_scenario(
            record,
            "C",
            started_at=c_started,
            entrypoints=[
                "POST /tasks",
                "POST /tasks/{id}/reminders",
                "POST /inbox",
                "POST /waiting-for",
                "POST /work-logs",
            ],
            actuals={
                "canonical prefixes": all(
                    value.startswith(prefix) for value, prefix in prefix_pairs
                ),
                "revisions recorded": all(
                    item["revision"] >= 1 for item in response_revisions
                ),
                "workspace recorded": all(
                    value in c_serialized
                    for value in (
                        "acc020-tenant",
                        "acc020-workspace",
                        "daily",
                    )
                ),
                "sqlite rows recorded": bool(c_snapshot["value"]["sqlite"]),
                "five domains created": len(canonical_ids) == 5,
                "canonical ids persisted": all(
                    item in c_serialized for item in canonical_ids
                ),
            },
            evidence_payload={
                "objects": {
                    "task": task,
                    "reminder": reminder,
                    "inbox": inbox,
                    "waiting_for": waiting,
                    "work_log": work_log,
                },
                "sqlite_path": c_snapshot["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=c_http_start,
                command_start=c_command_start,
                response_facts={"revisions": response_revisions},
                object_ids=canonical_ids,
                workspace=record["workspace"],
                revision_status=response_revisions,
                database_evidence=[c_snapshot["path"]],
                spy_evidence=["events.log", "scheduler.log"],
            ),
        )

        d_started = datetime.now(UTC).isoformat()
        d_http_start = len(record["http_operations"])
        d_command_start = len(record["commands"])
        d_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="d-before",
            secret=token,
        )
        d_event_before = len(_read_json_lines(spy_root / "events.log"))
        d_scheduler_before = len(_read_json_lines(spy_root / "scheduler.log"))
        _, agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _, agenda_repeat = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        d_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="d-after",
            secret=token,
        )
        agenda_ids = [
            item.get("source_id", item.get("id", ""))
            for section in agenda.get("sections", {}).values()
            if isinstance(section, dict)
            for item in section.get("items", [])
        ] if isinstance(agenda.get("sections"), dict) else [
            item.get("source_id", item.get("id", ""))
            for value in agenda.values()
            if isinstance(value, list)
            for item in value
            if isinstance(item, dict)
        ]
        agenda_repeat_ids = [
            item.get("source_id", item.get("id", ""))
            for item in agenda_repeat.get("items", [])
        ]
        d_side_effects_unchanged = (
            d_before["value"]["sqlite"] == d_after["value"]["sqlite"]
            and d_event_before == len(_read_json_lines(spy_root / "events.log"))
            and d_scheduler_before
            == len(_read_json_lines(spy_root / "scheduler.log"))
        )
        agenda_workspace = record["workspace"]
        _finish_scenario(
            record,
            "D",
            started_at=d_started,
            entrypoints=["GET /agenda", "GET /agenda repeated"],
            actuals={
                "agenda contains real objects": bool(
                    set(agenda_ids) & set(canonical_ids)
                ),
                "canonical ids match": all(
                    value in canonical_ids for value in agenda_ids
                ),
                "stable ordering": agenda_ids == agenda_repeat_ids,
                "repeat result deterministic": (
                    _without_volatile(agenda)
                    == _without_volatile(agenda_repeat)
                ),
                "complete workspace": all(
                    agenda_workspace.get(key) == value
                    for key, value in {
                        "tenant_id": "acc020-tenant",
                        "workspace_id": "acc020-workspace",
                        "namespace": "daily",
                    }.items()
                ),
                "read side effects unchanged": d_side_effects_unchanged,
            },
            evidence_payload={
                "agenda": agenda,
                "agenda_repeat": agenda_repeat,
                "agenda_ids": agenda_ids,
                "before": d_before["path"],
                "after": d_after["path"],
                "event_counts": [d_event_before, len(_read_json_lines(spy_root / "events.log"))],
                "scheduler_counts": [
                    d_scheduler_before,
                    len(_read_json_lines(spy_root / "scheduler.log")),
                ],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=d_http_start,
                command_start=d_command_start,
                response_facts={"agenda_ids": agenda_ids},
                object_ids=agenda_ids,
                workspace=record["workspace"],
                revision_status=[],
                database_evidence=[d_before["path"], d_after["path"]],
                spy_evidence=["events.log", "scheduler.log"],
            ),
        )
        e_started = datetime.now(UTC).isoformat()
        e_http_start = len(record["http_operations"])
        e_command_start = len(record["commands"])
        _, today = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, yesterday = _http(
            args,
            record,
            "GET",
            "/daily-review?date=yesterday",
            token=token,
            headers=workspace_headers,
        )
        cli_workspace = [
            "--tenant-id", "acc020-tenant",
            "--workspace-id", "acc020-workspace",
            "--namespace", "daily",
            "--session-id", "acc020-session",
            "--agent-id", "acc020-driver",
        ]
        cli_today_result = capture_command(
            [
                sys.executable,
                "-m",
                "cli",
                "daily-review",
                "--date",
                "today",
                *cli_workspace,
                "--json",
            ],
            env=env,
            cwd=repo,
            records=record["commands"],
            evidence=evidence,
            label="e-cli-today",
            expected_codes=(0,),
        )
        cli_yesterday_result = capture_command(
            [
                sys.executable,
                "-m",
                "cli",
                "daily-review",
                "--date",
                "yesterday",
                *cli_workspace,
                "--json",
            ],
            env=env,
            cwd=repo,
            records=record["commands"],
            evidence=evidence,
            label="e-cli-yesterday",
            expected_codes=(0,),
        )
        cli_today = json.loads(cli_today_result["stdout"])
        cli_yesterday = json.loads(cli_yesterday_result["stdout"])
        e_evidence = {
            "api_today": today,
            "api_yesterday": yesterday,
            "cli_today": cli_today,
            "cli_yesterday": cli_yesterday,
        }
        _finish_scenario(
            record,
            "E",
            started_at=e_started,
            entrypoints=[
                "GET /daily-review?date=today",
                "GET /daily-review?date=yesterday",
                "CLI daily-review --date today --json",
                "CLI daily-review --date yesterday --json",
            ],
            actuals={
                "api today": today.get("review_date") is not None,
                "api yesterday": yesterday.get("review_date") is not None,
                "cli today json": cli_today.get("review_date") == today.get("review_date"),
                "cli yesterday json": (
                    cli_yesterday.get("review_date")
                    == yesterday.get("review_date")
                ),
                "date and timezone match": (
                    today.get("timezone") == cli_today.get("timezone")
                    and yesterday.get("timezone")
                    == cli_yesterday.get("timezone")
                ),
                "period and source status match": all(
                    api_value.get(key) == cli_value.get(key)
                    for api_value, cli_value in (
                        (today, cli_today),
                        (yesterday, cli_yesterday),
                    )
                    for key in ("period_start", "period_end", "source_status")
                ),
                "canonical sections and pagination match": (
                    _review_ids(today) == _review_ids(cli_today)
                    and _review_ids(yesterday) == _review_ids(cli_yesterday)
                    and today.get("page") == cli_today.get("page")
                    and yesterday.get("page") == cli_yesterday.get("page")
                ),
                "only volatile instants differ": (
                    _normalized_review(today) == _normalized_review(cli_today)
                    and _normalized_review(yesterday)
                    == _normalized_review(cli_yesterday)
                ),
            },
            evidence_payload=e_evidence,
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=e_http_start,
                command_start=e_command_start,
                response_facts={
                    "today_ids": _review_ids(today),
                    "yesterday_ids": _review_ids(yesterday),
                    "source_status": today.get("source_status"),
                },
                object_ids=sorted(set(_review_ids(today) + _review_ids(yesterday))),
                workspace=record["workspace"],
                revision_status=[],
                database_evidence=[c_snapshot["path"]],
                spy_evidence=[
                    cli_today_result["stdout_path"],
                    cli_yesterday_result["stdout_path"],
                ],
            ),
        )

        f_started = datetime.now(UTC).isoformat()
        f_http_start = len(record["http_operations"])
        f_command_start = len(record["commands"])
        f_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="f-before",
            secret=token,
        )
        f_event_before = len(_read_json_lines(spy_root / "events.log"))
        f_scheduler_before = len(_read_json_lines(spy_root / "scheduler.log"))
        f_provider_before = len(counter.read_text(encoding="utf-8").splitlines())
        _, hints = _http(
            args,
            record,
            "GET",
            "/daily-review/action-hints?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, repeated_hints = _http(
            args,
            record,
            "GET",
            "/daily-review/action-hints?date=today",
            token=token,
            headers=workspace_headers,
        )
        from core.daily_review.action_hints import _DECISIONS
        unsupported_hints = _DECISIONS.get(
            ("work_log", "completed", "work_log.completed"),
            (),
        )
        f_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="f-after",
            secret=token,
        )
        hint_fields = {
            "source_type",
            "source_id",
            "status",
            "reason_code",
            "allowed_action",
            "required_arguments",
            "requires_revision",
            "requires_idempotency_key",
            "requires_confirmation",
            "requires_durable_claim",
            "saga_contract",
            "available_entrypoints",
        }
        reminder_hints = [
            hint for hint in hints if hint["source_type"] == "reminder"
        ]
        inbox_hints = [
            hint for hint in hints if hint["source_type"] == "inbox"
        ]
        inbox_actions = {
            hint["allowed_action"] for hint in inbox_hints
        }
        entrypoint_arguments = {
            ("user_task", "complete"): ("source_id", "expected_revision"),
            ("user_task", "cancel"): ("source_id", "expected_revision"),
            ("waiting_for", "follow_up"): (
                "source_id",
                "expected_revision",
                "note",
            ),
            ("reminder", "reschedule"): (
                "source_id",
                "expected_revision",
                "scheduled_for",
                "timezone",
            ),
            ("inbox", "resolve_to_task"): ("source_id", "title"),
            ("inbox", "resolve_to_reminder"): (
                "source_id",
                "title",
                "scheduled_at",
                "timezone",
            ),
            ("inbox", "resolve_to_work_log"): ("source_id", "title"),
            ("inbox", "resolve_to_waiting_for"): (
                "source_id",
                "subject",
                "waiting_on",
                "next_review_at",
                "timezone",
            ),
            ("inbox", "resolve_as_note"): ("source_id",),
            ("inbox", "dismiss"): ("source_id",),
        }
        callable_arguments = all(
            tuple(hint["required_arguments"])
            == entrypoint_arguments.get(
                (hint["source_type"], hint["allowed_action"]),
                (),
            )
            for hint in hints
        )
        f_side_effects_unchanged = (
            f_before["value"]["sqlite"] == f_after["value"]["sqlite"]
            and f_event_before == len(_read_json_lines(spy_root / "events.log"))
            and f_scheduler_before
            == len(_read_json_lines(spy_root / "scheduler.log"))
            and f_provider_before
            == len(counter.read_text(encoding="utf-8").splitlines())
        )
        f_event_after = len(_read_json_lines(spy_root / "events.log"))
        _finish_scenario(
            record,
            "F",
            started_at=f_started,
            entrypoints=[
                "GET /daily-review/action-hints?date=today",
                "core.daily_review.build_action_hints unsupported tuple",
            ],
            actuals={
                "repeated hints identical": hints == repeated_hints,
                "fields complete": bool(hints) and all(
                    set(hint) == hint_fields for hint in hints
                ),
                "required arguments callable": callable_arguments,
                "reminder idempotency optional": (
                    bool(reminder_hints)
                    and all(
                        not hint["requires_idempotency_key"]
                        and "idempotency_key" not in hint["required_arguments"]
                        for hint in reminder_hints
                    )
                ),
                "six inbox actions": inbox_actions == {
                    "resolve_to_task",
                    "resolve_to_reminder",
                    "resolve_to_work_log",
                    "resolve_to_waiting_for",
                    "resolve_as_note",
                    "dismiss",
                },
                "unsupported tuple empty": len(unsupported_hints) == 0,
                "hint side effects unchanged": f_side_effects_unchanged,
            },
            evidence_payload={
                "hints": hints,
                "repeated_hints": repeated_hints,
                "unsupported_count": len(unsupported_hints),
                "entrypoint_argument_contracts": {
                    f"{source_type}:{action}": list(arguments)
                    for (source_type, action), arguments
                    in entrypoint_arguments.items()
                },
                "before": f_before["path"],
                "after": f_after["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=f_http_start,
                command_start=f_command_start,
                response_facts={"hint_count": len(hints), "hints": hints},
                object_ids=sorted({hint["source_id"] for hint in hints}),
                workspace=record["workspace"],
                revision_status=[],
                database_evidence=[f_before["path"], f_after["path"]],
                spy_evidence=["events.log", "scheduler.log", "calls.log"],
            ),
        )

        g_started = datetime.now(UTC).isoformat()
        g_http_start = len(record["http_operations"])
        g_command_start = len(record["commands"])
        _, legacy_complete_task = _http(
            args,
            record,
            "POST",
            "/tasks",
            token=token,
            headers=workspace_headers,
            body={"title": "ACC-020 legacy complete"},
            expected=(201,),
        )
        _, legacy_cancel_task = _http(
            args,
            record,
            "POST",
            "/tasks",
            token=token,
            headers=workspace_headers,
            body={"title": "ACC-020 legacy cancel"},
            expected=(201,),
        )
        _, cross_task = _http(
            args,
            record,
            "POST",
            "/tasks",
            token=token,
            headers=workspace_headers,
            body={"title": "ACC-020 workspace mutation"},
            expected=(201,),
        )
        update_stale_status, update_stale = _http(
            args,
            record,
            "PATCH",
            f"/tasks/{task['id']}",
            token=token,
            headers=workspace_headers,
            body={"title": "stale", "revision": task["revision"] + 99},
            expected=(409,),
        )
        legacy_complete_status, legacy_completed = _http(
            args,
            record,
            "POST",
            f"/tasks/{legacy_complete_task['id']}/complete",
            token=token,
            headers=workspace_headers,
        )
        legacy_cancel_status, legacy_cancelled = _http(
            args,
            record,
            "POST",
            f"/tasks/{legacy_cancel_task['id']}/cancel",
            token=token,
            headers=workspace_headers,
        )
        missing_revision_status, missing_revision = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={},
            expected=(400,),
        )
        stale_active_status, stale_active = _http(
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
        terminal_stale_status, terminal_stale = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={"expected_revision": task["revision"]},
            expected=(409,),
        )
        terminal_exact_status, terminal_exact = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={"expected_revision": completed["revision"]},
        )
        cross_mutation_status, cross_mutation = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{cross_task['id']}/complete",
            token=token,
            headers={**workspace_headers, "X-Workspace-ID": "isolated"},
            body={"expected_revision": cross_task["revision"]},
            expected=(404,),
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
        g_snapshot = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="g-user-task-sqlite",
            secret=token,
        )
        g_sqlite = json.dumps(g_snapshot["value"]["sqlite"], ensure_ascii=False)
        safe_public_fields = (
            "workspace" not in completed
            and "legacy_source_id" not in completed
        )
        g_revision_status = [
            {
                "id": task["id"],
                "before_revision": task["revision"],
                "after_revision": completed["revision"],
                "status": completed["status"],
            },
            {
                "id": legacy_complete_task["id"],
                "revision": legacy_completed["revision"],
                "status": legacy_completed["status"],
            },
            {
                "id": legacy_cancel_task["id"],
                "revision": legacy_cancelled["revision"],
                "status": legacy_cancelled["status"],
            },
        ]
        _finish_scenario(
            record,
            "G",
            started_at=g_started,
            entrypoints=[
                "PATCH /tasks/{id}",
                "POST /tasks/{id}/complete",
                "POST /tasks/{id}/cancel",
                "POST /daily-review/actions/user-tasks/{id}/complete",
            ],
            actuals={
                "update stale": update_stale_status == 409,
                "legacy complete compatibility": (
                    legacy_complete_status == 200
                    and legacy_completed["status"] == "completed"
                ),
                "legacy cancel compatibility": (
                    legacy_cancel_status == 200
                    and legacy_cancelled["status"] == "cancelled"
                ),
                "review missing revision": missing_revision_status == 400,
                "active stale revision": stale_active_status == 409,
                "terminal stale revision": terminal_stale_status == 409,
                "terminal exact revision": (
                    terminal_exact_status == 200
                    and terminal_exact["revision"] == completed["revision"]
                    and terminal_exact["status"] == "completed"
                ),
                "cross workspace mutation": cross_mutation_status == 404,
                "public task response": safe_public_fields,
                "sqlite revision status": (
                    task["id"] in g_sqlite
                    and str(completed["revision"]) in g_sqlite
                    and "completed" in g_sqlite
                ),
            },
            evidence_payload={
                "failures": {
                    "update_stale": update_stale,
                    "missing_revision": missing_revision,
                    "active_stale": stale_active,
                    "terminal_stale": terminal_stale,
                    "cross_workspace": cross_mutation,
                },
                "completed": completed,
                "terminal_exact": terminal_exact,
                "legacy_completed": legacy_completed,
                "legacy_cancelled": legacy_cancelled,
                "sqlite_path": g_snapshot["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=g_http_start,
                command_start=g_command_start,
                response_facts={
                    "failures": [
                        update_stale,
                        missing_revision,
                        stale_active,
                        terminal_stale,
                        cross_mutation,
                    ],
                },
                object_ids=[
                    task["id"],
                    legacy_complete_task["id"],
                    legacy_cancel_task["id"],
                    cross_task["id"],
                ],
                workspace=record["workspace"],
                revision_status=g_revision_status,
                database_evidence=[g_snapshot["path"]],
                spy_evidence=["events.log"],
            ),
        )

        h_started = datetime.now(UTC).isoformat()
        h_http_start = len(record["http_operations"])
        h_command_start = len(record["commands"])
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
        _, snoozed = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/snooze",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": followed["item"]["revision"],
                "next_review_at": (now + timedelta(hours=3)).isoformat(),
                "note": "ACC-020 snooze",
            },
        )
        _, waiting_resolved = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/resolve",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": snoozed["item"]["revision"],
                "resolution_note": "ACC-020 resolved",
            },
        )
        _, reopened = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/reopen",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": waiting_resolved["item"]["revision"],
                "note": "ACC-020 reopen",
                "next_review_at": (now + timedelta(hours=4)).isoformat(),
            },
        )
        _, waiting_cancelled = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/cancel",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": reopened["item"]["revision"],
                "note": "ACC-020 cancel",
            },
        )
        _, waiting_history = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}/events",
            token=token,
            headers=workspace_headers,
        )
        h_stale_status, h_stale = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/follow-ups",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": waiting["item"]["revision"],
                "note": "stale",
            },
            expected=(409,),
        )
        h_unsupported_status, h_unsupported = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{waiting['item']['id']}/follow-ups",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": waiting_cancelled["item"]["revision"],
                "note": "unsupported",
            },
            expected=(409,),
        )
        _, missing_waiting = _http(
            args,
            record,
            "POST",
            "/waiting-for",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 missing argument",
                "waiting_on": "Owner",
                "timezone": "UTC",
            },
            expected=(201,),
        )
        h_missing_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="h-missing-before",
            secret=token,
        )
        h_missing_status, h_missing = _http(
            args,
            record,
            "POST",
            f"/waiting-for/{missing_waiting['item']['id']}/snooze",
            token=token,
            headers=workspace_headers,
            body={
                "expected_revision": missing_waiting["item"]["revision"],
                "note": "missing next review",
            },
            expected=(400, 422),
        )
        h_missing_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="h-missing-after",
            secret=token,
        )
        h_revisions = [
            waiting["item"]["revision"],
            followed["item"]["revision"],
            snoozed["item"]["revision"],
            waiting_resolved["item"]["revision"],
            reopened["item"]["revision"],
            waiting_cancelled["item"]["revision"],
        ]
        history_types = [
            item["event_type"] for item in waiting_history["items"]
        ]
        _finish_scenario(
            record,
            "H",
            started_at=h_started,
            entrypoints=[
                "POST /waiting-for/{id}/follow-ups",
                "POST /waiting-for/{id}/snooze",
                "POST /waiting-for/{id}/resolve",
                "POST /waiting-for/{id}/reopen",
                "POST /waiting-for/{id}/cancel",
                "GET /waiting-for/{id}/events",
            ],
            actuals={
                "follow up": followed["item"]["status"] == "open",
                "resolve": waiting_resolved["item"]["status"] == "resolved",
                "snooze": snoozed["item"]["next_review_at"] is not None,
                "cancel": waiting_cancelled["item"]["status"] == "cancelled",
                "reopen": reopened["item"]["status"] == "open",
                "history event": set(history_types) >= {
                    "created",
                    "followed_up",
                    "snoozed",
                    "resolved",
                    "reopened",
                    "cancelled",
                },
                "revision progression": h_revisions == sorted(set(h_revisions)),
                "stale revision": h_stale_status == 409,
                "unsupported state": h_unsupported_status == 409,
                "missing argument no write": (
                    h_missing_status in {400, 422}
                    and h_missing_before["value"]["sqlite"]
                    == h_missing_after["value"]["sqlite"]
                ),
            },
            evidence_payload={
                "states": {
                    "followed": followed,
                    "snoozed": snoozed,
                    "resolved": waiting_resolved,
                    "reopened": reopened,
                    "cancelled": waiting_cancelled,
                },
                "history": waiting_history,
                "stale_failure": h_stale,
                "unsupported_failure": h_unsupported,
                "missing_failure": h_missing,
                "missing_before": h_missing_before["path"],
                "missing_after": h_missing_after["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=h_http_start,
                command_start=h_command_start,
                response_facts={"history_types": history_types},
                object_ids=[
                    waiting["item"]["id"],
                    missing_waiting["item"]["id"],
                ],
                workspace=record["workspace"],
                revision_status=[
                    {"id": waiting["item"]["id"], "revisions": h_revisions},
                ],
                database_evidence=[
                    h_missing_before["path"],
                    h_missing_after["path"],
                ],
                spy_evidence=["events.log"],
            ),
        )

        i_started = datetime.now(UTC).isoformat()
        i_http_start = len(record["http_operations"])
        i_command_start = len(record["commands"])
        i_missing_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="i-missing-before",
            secret=token,
        )
        i_missing_status, i_missing = _http(
            args,
            record,
            "POST",
            f"/inbox/{inbox['id']}/resolve/waiting-for",
            token=token,
            headers=workspace_headers,
            body={"subject": "Missing", "waiting_on": "Owner"},
            expected=(400,),
        )
        i_missing_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="i-missing-after",
            secret=token,
        )
        _, resolved_inbox = _http(
            args,
            record,
            "POST",
            f"/inbox/{inbox['id']}/resolve/waiting-for",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 Inbox Waiting-For",
                "waiting_on": "Owner",
                "next_review_at": (now + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
            },
        )
        record["claims_and_sagas"].append({
            "inbox_id": inbox["id"],
            "resolved_type": resolved_inbox["resolved_type"],
        })
        _, replayed_inbox = _http(
            args,
            record,
            "POST",
            f"/inbox/{inbox['id']}/resolve/waiting-for",
            token=token,
            headers=workspace_headers,
            body={
                "subject": "ACC-020 Inbox Waiting-For",
                "waiting_on": "Owner",
                "next_review_at": (now + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
            },
        )
        i_competing_status, i_competing = _http(
            args,
            record,
            "POST",
            f"/inbox/{inbox['id']}/resolve/task",
            token=token,
            headers=workspace_headers,
            body={"title": "competing target"},
            expected=(409,),
        )
        _, note_inbox = _http(
            args,
            record,
            "POST",
            "/inbox",
            token=token,
            headers=workspace_headers,
            body={"content": "ACC-020 note resolution"},
            expected=(201,),
        )
        _, note_resolved = _http(
            args,
            record,
            "POST",
            f"/inbox/{note_inbox['id']}/resolve/note",
            token=token,
            headers=workspace_headers,
        )
        i_snapshot = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="i-inbox-claim-sqlite",
            secret=token,
        )
        i_sqlite = json.dumps(i_snapshot["value"]["sqlite"], ensure_ascii=False)
        target_id = resolved_inbox.get("resolved_target_id")
        _finish_scenario(
            record,
            "I",
            started_at=i_started,
            entrypoints=[
                "POST /inbox/{id}/resolve/waiting-for",
                "POST /inbox/{id}/resolve/task",
                "POST /inbox/{id}/resolve/note",
            ],
            actuals={
                "target resolution": (
                    resolved_inbox["resolved_type"] == "waiting_for"
                    and bool(target_id)
                ),
                "note or dismiss": note_resolved["resolved_type"] == "note",
                "missing waiting confirmation": (
                    i_missing_status == 400
                    and i_missing_before["value"]["sqlite"]
                    == i_missing_after["value"]["sqlite"]
                ),
                "resolution replay": (
                    replayed_inbox.get("resolved_target_id") == target_id
                ),
                "competing resolution": i_competing_status == 409,
                "durable claim": (
                    inbox["id"] in i_sqlite
                    and "completed" in i_sqlite.lower()
                ),
                "target id": bool(target_id and target_id.startswith("wf_")),
                "source resolved": resolved_inbox["status"] == "resolved",
                "single target": (
                    replayed_inbox.get("resolved_target_id") == target_id
                    and not i_competing.get("resolved_target_id")
                ),
            },
            evidence_payload={
                "missing_failure": i_missing,
                "resolved": resolved_inbox,
                "replayed": replayed_inbox,
                "competing_failure": i_competing,
                "note": note_resolved,
                "sqlite_path": i_snapshot["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=i_http_start,
                command_start=i_command_start,
                response_facts={
                    "target_id": target_id,
                    "resolved_status": resolved_inbox["status"],
                },
                object_ids=[
                    inbox["id"],
                    target_id,
                    note_inbox["id"],
                ],
                workspace=record["workspace"],
                revision_status=[],
                database_evidence=[
                    i_missing_before["path"],
                    i_missing_after["path"],
                    i_snapshot["path"],
                ],
                spy_evidence=["events.log"],
            ),
        )

        j_started = datetime.now(UTC).isoformat()
        j_http_start = len(record["http_operations"])
        j_command_start = len(record["commands"])
        j_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="j-before-read",
            secret=token,
        )
        j_event_before = len(_read_json_lines(spy_root / "events.log"))
        j_scheduler_before = len(_read_json_lines(spy_root / "scheduler.log"))
        _, refreshed_review = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        j_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="j-after-read",
            secret=token,
        )
        refreshed_ids = _review_ids(refreshed_review)
        completed_ids = [
            item["source_id"]
            for item in refreshed_review.get("completed", {}).get("items", [])
        ]
        pending_inbox_ids = [
            item["source_id"]
            for item in refreshed_review.get("pending_inbox", {}).get("items", [])
        ]
        informational_waiting = [
            item
            for item in refreshed_review.get("informational", {}).get("items", [])
            if item["source_id"] == waiting_cancelled["item"]["id"]
        ]
        j_side_effects = (
            j_before["value"]["sqlite"] == j_after["value"]["sqlite"]
            and j_event_before == len(_read_json_lines(spy_root / "events.log"))
            and j_scheduler_before
            == len(_read_json_lines(spy_root / "scheduler.log"))
        )
        j_event_after = len(_read_json_lines(spy_root / "events.log"))
        _finish_scenario(
            record,
            "J",
            started_at=j_started,
            entrypoints=["GET /daily-review?date=today after mutations"],
            actuals={
                "terminal task reclassified": task["id"] in completed_ids,
                "waiting history reflected": (
                    len(informational_waiting) == 1
                    and informational_waiting[0]["status"] == "cancelled"
                    and informational_waiting[0]["reason_code"]
                    == "waiting_for.cancelled"
                    and len(waiting_history["items"]) >= 6
                ),
                "pending inbox removed": inbox["id"] not in pending_inbox_ids,
                "no duplicates": len(refreshed_ids) == len(set(refreshed_ids)),
                "no omissions": all(
                    value in refreshed_ids
                    for value in (task["id"], work_log["id"])
                ),
                "no snapshot or automatic mutation": j_side_effects,
            },
            evidence_payload={
                "before_review": today,
                "after_review": refreshed_review,
                "before_sqlite": j_before["path"],
                "after_sqlite": j_after["path"],
                "event_counts": [
                    j_event_before,
                    len(_read_json_lines(spy_root / "events.log")),
                ],
                "scheduler_counts": [
                    j_scheduler_before,
                    len(_read_json_lines(spy_root / "scheduler.log")),
                ],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=j_http_start,
                command_start=j_command_start,
                response_facts={
                    "review_ids": refreshed_ids,
                    "completed_ids": completed_ids,
                    "pending_inbox_ids": pending_inbox_ids,
                },
                object_ids=refreshed_ids,
                workspace=record["workspace"],
                revision_status=[
                    {
                        "id": task["id"],
                        "status": completed["status"],
                        "revision": completed["revision"],
                    },
                    {
                        "id": waiting_cancelled["item"]["id"],
                        "status": waiting_cancelled["item"]["status"],
                        "revision": waiting_cancelled["item"]["revision"],
                    },
                ],
                database_evidence=[j_before["path"], j_after["path"]],
                spy_evidence=["events.log", "scheduler.log"],
            ),
        )

        k_started = datetime.now(UTC).isoformat()
        k_http_start = len(record["http_operations"])
        k_command_start = len(record["commands"])
        isolated_headers = {
            **workspace_headers,
            "X-Workspace-ID": "isolated",
        }
        k_task_status, k_task = _http(
            args,
            record,
            "GET",
            f"/tasks/{task['id']}",
            token=token,
            headers=isolated_headers,
            expected=(404,),
        )
        k_mutation_status, k_mutation = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{cross_task['id']}/complete",
            token=token,
            headers=isolated_headers,
            body={"expected_revision": cross_task["revision"]},
            expected=(404,),
        )
        _, k_agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=isolated_headers,
        )
        _, k_review = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=isolated_headers,
        )
        _, k_hints = _http(
            args,
            record,
            "GET",
            "/daily-review/action-hints?date=today",
            token=token,
            headers=isolated_headers,
        )
        isolated_env = dict(env)
        isolated_env["AI_LAB_WORKSPACE_ID"] = "isolated"
        k_cli = capture_command(
            [
                sys.executable,
                "-m",
                "cli",
                "daily-review",
                "--date",
                "today",
                "--workspace-id",
                "isolated",
                "--json",
            ],
            env=isolated_env,
            cwd=repo,
            records=record["commands"],
            evidence=evidence,
            label="k-cli-isolated",
            expected_codes=(0,),
        )
        k_cli_review = json.loads(k_cli["stdout"])
        k_ceo = capture_command(
            [sys.executable, "-m", "cli", "ceo"],
            env=isolated_env,
            cwd=repo,
            records=record["commands"],
            evidence=evidence,
            label="k-ceo-isolated",
            expected_codes=(0,),
            input_text="/tasks\n/exit\n",
        )
        primary_ids = set(canonical_ids)
        k_agenda_ids = {
            item.get("source_id")
            for item in k_agenda.get("items", [])
        }
        k_review_ids = set(_review_ids(k_review))
        k_cli_ids = set(_review_ids(k_cli_review))
        k_hint_ids = {item["source_id"] for item in k_hints}
        _finish_scenario(
            record,
            "K",
            started_at=k_started,
            entrypoints=[
                "API Task GET and mutation with Workspace B",
                "API Agenda, Review, Hint with Workspace B",
                "CLI Daily Review with Workspace B",
                "CEO Assistant /tasks with Workspace B",
            ],
            actuals={
                "task invisible": k_task_status == 404,
                "mutation blocked": k_mutation_status == 404,
                "agenda invisible": not (primary_ids & k_agenda_ids),
                "review invisible": not (primary_ids & k_review_ids),
                "hint invisible": not (primary_ids & k_hint_ids),
                "cli invisible": not (primary_ids & k_cli_ids),
                "ceo invisible": all(
                    value not in k_ceo["stdout"]
                    for value in primary_ids
                ),
                "no default fallback": (
                    k_cli_review.get("workspace", {}).get("workspace_id")
                    == "isolated"
                    and "default" not in {
                        k_cli_review.get("workspace", {}).get("workspace_id"),
                        k_review.get("workspace", {}).get("workspace_id"),
                    }
                ),
            },
            evidence_payload={
                "task_failure": k_task,
                "mutation_failure": k_mutation,
                "agenda": k_agenda,
                "review": k_review,
                "hints": k_hints,
                "cli_review": k_cli_review,
                "cli_stdout_path": k_cli["stdout_path"],
                "ceo_stdout_path": k_ceo["stdout_path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=k_http_start,
                command_start=k_command_start,
                response_facts={
                    "api_ids": sorted(k_review_ids),
                    "cli_ids": sorted(k_cli_ids),
                    "hint_ids": sorted(k_hint_ids),
                },
                object_ids=sorted(primary_ids),
                workspace={
                    **record["workspace"],
                    "workspace_id": "isolated",
                },
                revision_status=[],
                database_evidence=[j_after["path"]],
                spy_evidence=[k_cli["stdout_path"], k_ceo["stdout_path"]],
            ),
        )

        m_started = datetime.now(UTC).isoformat()
        m_http_start = len(record["http_operations"])
        m_command_start = len(record["commands"])
        m_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="m-before-failures",
            secret=token,
        )
        m_event_before = len(_read_json_lines(spy_root / "events.log"))
        m_scheduler_before = len(_read_json_lines(spy_root / "scheduler.log"))
        m_missing_id_status, m_missing_id = _http(
            args,
            record,
            "GET",
            "/tasks/ut_missing_acc020",
            token=token,
            headers=workspace_headers,
            expected=(404,),
        )
        m_missing_revision_status, m_missing_revision = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{cross_task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={},
            expected=(400,),
        )
        m_stale_status, m_stale = _http(
            args,
            record,
            "POST",
            f"/daily-review/actions/user-tasks/{cross_task['id']}/complete",
            token=token,
            headers=workspace_headers,
            body={"expected_revision": cross_task["revision"] + 10},
            expected=(409,),
        )
        m_work_log_status, m_work_log = _http(
            args,
            record,
            "POST",
            f"/work-logs/{work_log['id']}/complete",
            token=token,
            headers=workspace_headers,
            expected=(404, 405),
        )
        invalid_tuple_empty = len(
            _DECISIONS.get(("inbox", "resolved", "inbox.pending"), ())
        ) == 0
        m_failures_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="m-after-core-failures",
            secret=token,
        )
        _, m_inbox = _http(
            args,
            record,
            "POST",
            "/inbox",
            token=token,
            headers=workspace_headers,
            body={"content": "ACC-020 missing required argument"},
            expected=(201,),
        )
        m_required_before = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="m-required-before",
            secret=token,
        )
        m_event_after_setup = len(_read_json_lines(spy_root / "events.log"))
        m_required_status, m_required = _http(
            args,
            record,
            "POST",
            f"/inbox/{m_inbox['id']}/resolve/task",
            token=token,
            headers=workspace_headers,
            body={},
            expected=(400,),
        )
        m_after = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="m-after-failures",
            secret=token,
        )
        m_event_after = len(_read_json_lines(spy_root / "events.log"))
        m_scheduler_after = len(_read_json_lines(spy_root / "scheduler.log"))
        _finish_scenario(
            record,
            "M",
            started_at=m_started,
            entrypoints=[
                "missing canonical Task GET",
                "Review action missing and stale revision",
                "unsupported Work Log mutation",
                "Waiting-For resolution missing confirmation",
                "Inbox resolution missing required argument",
                "unsupported Action Hint tuple",
            ],
            actuals={
                "missing canonical id unchanged": (
                    m_missing_id_status == 404
                    and m_before["value"]["sqlite"]
                    == m_failures_after["value"]["sqlite"]
                ),
                "missing revision unchanged": (
                    m_missing_revision_status == 400
                    and m_before["value"]["sqlite"]
                    == m_failures_after["value"]["sqlite"]
                ),
                "stale revision unchanged": (
                    m_stale_status == 409
                    and m_before["value"]["sqlite"]
                    == m_failures_after["value"]["sqlite"]
                ),
                "invalid status reason unchanged": (
                    invalid_tuple_empty
                    and m_before["value"]["sqlite"]
                    == m_failures_after["value"]["sqlite"]
                ),
                "unsupported work log mutation unchanged": (
                    m_work_log_status in {404, 405}
                    and m_before["value"]["sqlite"]
                    == m_failures_after["value"]["sqlite"]
                ),
                "waiting confirmation unchanged": (
                    i_missing_before["value"]["sqlite"]
                    == i_missing_after["value"]["sqlite"]
                ),
                "required arguments unchanged": (
                    m_required_status == 400
                    and m_required_before["value"]["sqlite"]
                    == m_after["value"]["sqlite"]
                ),
                "event scheduler revision unchanged": (
                    m_event_after == m_event_after_setup
                    and m_scheduler_after == m_scheduler_before
                    and cross_task["revision"]
                    == (
                        _http(
                            args,
                            record,
                            "GET",
                            f"/tasks/{cross_task['id']}",
                            token=token,
                            headers=workspace_headers,
                        )[1]["revision"]
                    )
                ),
            },
            evidence_payload={
                "before": m_before["path"],
                "after_core_failures": m_failures_after["path"],
                "required_before": m_required_before["path"],
                "after": m_after["path"],
                "failures": {
                    "missing_id": m_missing_id,
                    "missing_revision": m_missing_revision,
                    "stale": m_stale,
                    "unsupported_work_log": m_work_log,
                    "required_argument": m_required,
                    "waiting_confirmation": i_missing,
                },
                "event_counts": [m_event_before, m_event_after],
                "scheduler_counts": [m_scheduler_before, m_scheduler_after],
                "successful_setup_write": m_inbox["id"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=m_http_start,
                command_start=m_command_start,
                response_facts={
                    "failure_statuses": [
                        m_missing_id_status,
                        m_missing_revision_status,
                        m_stale_status,
                        m_work_log_status,
                        m_required_status,
                    ],
                },
                object_ids=[cross_task["id"], work_log["id"], m_inbox["id"]],
                workspace=record["workspace"],
                revision_status=[
                    {
                        "id": cross_task["id"],
                        "revision": cross_task["revision"],
                    }
                ],
                database_evidence=[
                    m_before["path"],
                    m_failures_after["path"],
                    m_required_before["path"],
                    m_after["path"],
                    i_missing_before["path"],
                    i_missing_after["path"],
                ],
                spy_evidence=["events.log", "scheduler.log"],
            ),
        )

        o_started = datetime.now(UTC).isoformat()
        o_http_start = len(record["http_operations"])
        o_command_start = len(record["commands"])
        _, scheduler_task = _http(
            args,
            record,
            "POST",
            "/tasks",
            token=token,
            headers=workspace_headers,
            body={"title": "ACC-020 one-shot scheduler task"},
            expected=(201,),
        )
        _, reminder = _http(
            args,
            record,
            "POST",
            f"/tasks/{scheduler_task['id']}/reminders",
            token=token,
            headers=workspace_headers,
            body={
                "remind_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                "timezone": "UTC",
            },
            expected=(201,),
        )
        record["canonical_ids"].extend([scheduler_task["id"], reminder["id"]])
        _, current_reminder = _http(
            args,
            record,
            "GET",
            f"/reminders/{reminder['id']}/status",
            token=token,
            headers=workspace_headers,
        )
        idempotency_key = "acc020-reminder-reschedule"
        replay_body = {
            "scheduled_for": (now + timedelta(minutes=5)).isoformat(),
            "timezone": "UTC",
            "revision": current_reminder["revision"],
        }
        _, reminder_keyed = _http(
            args,
            record,
            "PATCH",
            f"/reminders/{reminder['id']}",
            token=token,
            headers={
                **workspace_headers,
                "Idempotency-Key": idempotency_key,
            },
            body=replay_body,
        )
        _, reminder_replayed = _http(
            args,
            record,
            "PATCH",
            f"/reminders/{reminder['id']}",
            token=token,
            headers={
                **workspace_headers,
                "Idempotency-Key": idempotency_key,
            },
            body=replay_body,
        )
        _, reminder_status = _http(
            args,
            record,
            "PATCH",
            f"/reminders/{reminder['id']}",
            token=token,
            headers=workspace_headers,
            body={
                "scheduled_for": (
                    datetime.now(UTC) + timedelta(seconds=2)
                ).isoformat(),
                "timezone": "UTC",
                "revision": reminder_keyed["revision"],
            },
        )
        record["idempotency_keys"].append(idempotency_key)
        record["mutations"].append({
            "domain": "reminder",
            "id": reminder["id"],
            "status": reminder_status["status"],
        })
        for _ in range(40):
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
        if reminder_status["status"] != "triggered":
            raise ProductAcceptanceError(
                "one-shot Reminder did not reach triggered"
            )
        for _ in range(4):
            time.sleep(0.15)
            _, health = _http(args, record, "GET", "/health")
            record["health_snapshots"].append(health)
            record["connection_counts"].append(
                health["database_connections"]
            )
        o_snapshot = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="o-scheduler-sqlite",
            secret=token,
        )
        o_sqlite = o_snapshot["value"]["sqlite"]
        flattened_rows = [
            row
            for database in o_sqlite.values()
            for rows in database["tables"].values()
            for row in rows
        ]
        job_rows = [
            row for row in flattened_rows
            if row.get("id") == reminder_status.get("scheduler_job_id")
            or row.get("job_id") == reminder_status.get("scheduler_job_id")
        ]
        occurrence_rows = [
            row for row in flattened_rows
            if row.get("reminder_id") == reminder["id"]
        ]
        run_rows = [
            row for row in flattened_rows
            if row.get("job_id") == reminder_status.get("scheduler_job_id")
            and ("run_id" in row or "attempt" in row)
        ]
        run_count_before_idle = len(run_rows)
        time.sleep(0.4)
        o_idle_snapshot = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="o-idle-sqlite",
            secret=token,
        )
        idle_rows = [
            row
            for database in o_idle_snapshot["value"]["sqlite"].values()
            for rows in database["tables"].values()
            for row in rows
            if row.get("job_id") == reminder_status.get("scheduler_job_id")
            and ("run_id" in row or "attempt" in row)
        ]
        o_scheduler_spy = _read_json_lines(spy_root / "scheduler.log")
        _finish_scenario(
            record,
            "O",
            started_at=o_started,
            entrypoints=[
                "PATCH /reminders/{id} optional idempotency",
                "GET /reminders/{id}/status polling",
                "GET /health periodic snapshots",
                "SQLite jobs/job_runs/reminder_occurrences",
            ],
            actuals={
                "multiple ticks": len(record["health_snapshots"]) >= 4,
                "one shot job": reminder_status["status"] == "triggered",
                "job status revision": any(
                    row.get("revision", 0) >= 1 for row in job_rows
                ),
                "run status": any(
                    str(row.get("status", "")).lower()
                    in {"success", "succeeded", "completed"}
                    for row in run_rows
                ),
                "claim token expiry": any(
                    bool(row.get("claim_token")) for row in run_rows
                ),
                "occurrence": bool(occurrence_rows),
                "reminder reconciliation": (
                    reminder_status.get("reminder_status") == "triggered"
                    and reminder_status.get("occurrence_status") == "triggered"
                ),
                "effectively once": (
                    len(run_rows) == 1 and len(occurrence_rows) == 1
                ),
                "idle window": len(idle_rows) == run_count_before_idle,
                "health and background tasks": all(
                    value.get("lifecycle") == "ready"
                    and isinstance(value.get("background_tasks"), int)
                    and value.get("background_tasks", -1) >= 0
                    for value in record["health_snapshots"]
                ),
                "real connection count": all(
                    isinstance(value, int) and value > 0
                    for value in record["connection_counts"]
                ),
            },
            evidence_payload={
                "keyed": reminder_keyed,
                "replayed": reminder_replayed,
                "triggered": reminder_status,
                "health_snapshots": record["health_snapshots"],
                "job_rows": job_rows,
                "run_rows": run_rows,
                "occurrence_rows": occurrence_rows,
                "scheduler_spy": o_scheduler_spy,
                "sqlite_path": o_snapshot["path"],
                "idle_sqlite_path": o_idle_snapshot["path"],
            },
            evidence_dir=evidence,
            secret=token,
            facts=_scenario_facts(
                record,
                http_start=o_http_start,
                command_start=o_command_start,
                response_facts={
                    "reminder_status": reminder_status,
                    "job_rows": job_rows,
                    "run_rows": run_rows,
                    "occurrence_rows": occurrence_rows,
                },
                object_ids=[
                    reminder["id"],
                    reminder_status.get("scheduler_job_id"),
                    reminder_status.get("occurrence_id"),
                ],
                workspace=record["workspace"],
                revision_status=[
                    {
                        "id": reminder["id"],
                        "revision": reminder_status["revision"],
                        "status": reminder_status["status"],
                    }
                ],
                database_evidence=[
                    o_snapshot["path"],
                    o_idle_snapshot["path"],
                ],
                spy_evidence=["scheduler.log"],
            ),
        )
        _, source_task = _http(
            args,
            record,
            "GET",
            f"/tasks/{task['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, source_reminder = _http(
            args,
            record,
            "GET",
            f"/reminders/{reminder['id']}/status",
            token=token,
            headers=workspace_headers,
        )
        _, source_waiting = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, source_waiting_history = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}/events",
            token=token,
            headers=workspace_headers,
        )
        _, source_inbox = _http(
            args,
            record,
            "GET",
            f"/inbox/{inbox['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, source_work_log = _http(
            args,
            record,
            "GET",
            f"/work-logs/{work_log['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, source_agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _, source_today = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, source_yesterday = _http(
            args,
            record,
            "GET",
            "/daily-review?date=yesterday",
            token=token,
            headers=workspace_headers,
        )
        source_sqlite = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="source-state-sqlite",
            secret=token,
        )
        source_state = {
            "task": source_task,
            "reminder": source_reminder,
            "waiting": source_waiting,
            "waiting_history": source_waiting_history,
            "inbox": source_inbox,
            "work_log": source_work_log,
            "agenda": _without_volatile(source_agenda),
            "today": _normalized_review(source_today),
            "yesterday": _normalized_review(source_yesterday),
            "sqlite": source_sqlite["value"]["sqlite"],
        }
        source_state_path = _write_json(
            evidence / "source-operating-state.json",
            source_state,
            secret=token,
        )
        _write_manifest(manifest_path, record)
    finally:
        exit_code = _stop_api(process, stdout, stderr)
    _assert_graceful_shutdown(
        exit_code=exit_code,
        stderr_path=evidence / "source-api-stderr.log",
        label="source",
    )
    shutdown_observations = _read_json_lines(spy_root / "shutdown.log")
    record["shutdown_observations"] = shutdown_observations
    q_started = datetime.now(UTC).isoformat()
    q_command_start = len(record["commands"])
    q_before_events = len(_read_json_lines(spy_root / "events.log"))
    q_before_scheduler = len(_read_json_lines(spy_root / "scheduler.log"))
    q_probe = _partial_start_probe(
        repo=repo,
        env=env,
        evidence=evidence,
        record=record,
    )
    record["partial_start_probe"] = q_probe
    q_shutdown = _read_json_lines(spy_root / "shutdown.log")
    record["shutdown_observations"] = q_shutdown
    q_new_shutdown = q_shutdown[len(shutdown_observations):]
    q_events_after = len(_read_json_lines(spy_root / "events.log"))
    q_scheduler_after = len(_read_json_lines(spy_root / "scheduler.log"))
    q_order = [item.get("event") for item in q_new_shutdown]
    source_shutdown = [
        item
        for item in shutdown_observations
        if item.get("pid") == record["api_pid"]
    ]
    source_shutdown_events = [item.get("event") for item in source_shutdown]
    source_health_after = [
        item
        for item in source_shutdown
        if item.get("event") == "container_shutdown_after"
    ]
    observed_zero = any(
        item.get("connections") == 0
        for item in source_shutdown
        if item.get("event") == "database_close_after"
    )
    if observed_zero:
        record["connection_counts"].append(0)
    p_started = datetime.now(UTC).isoformat()
    p_order = {
        event: source_shutdown_events.index(event)
        for event in source_shutdown_events
        if event in {
            "scheduler_shutdown_after",
            "event_bus_stop_after",
            "database_close_before",
        }
    }
    p_terminal = source_health_after[-1] if source_health_after else {}
    stopped_services = {
        item.get("service")
        for item in source_shutdown
        if item.get("event") == "service_close_after"
    }
    _finish_scenario(
        record,
        "P",
        started_at=p_started,
        entrypoints=["SIGINT Uvicorn", "SystemContainer.shutdown observer"],
        actuals={
            "ready draining terminal": (
                any(item.get("event") == "container_shutdown_before" for item in source_shutdown)
                and q_probe.get("draining_lifecycle") == "draining"
                and p_terminal.get("lifecycle") in {"stopped", "failed"}
            ),
            "draining rejects work": any(
                item.get("event") == "container_shutdown_before"
                and item.get("lifecycle") in {"ready", "draining"}
                for item in source_shutdown
            ) and bool(q_probe["draining_error"]),
            "background tasks converge": p_terminal.get("background_tasks") == 0,
            "scheduler services bus stop": {
                "scheduler_shutdown_after",
                "event_bus_stop_after",
            } <= set(source_shutdown_events)
            and {
                "reminder",
                "waiting_for",
                "inbox",
                "work_log",
                "user_task",
            } <= stopped_services,
            "database closes last": (
                p_order.get("database_close_before", -1)
                > p_order.get("scheduler_shutdown_after", -1)
                and p_order.get("database_close_before", -1)
                > p_order.get("event_bus_stop_after", -1)
            ),
            "connection count zero observed": observed_zero,
            "shutdown failures recorded": "shutdown_failures" in p_terminal,
            "graceful process exit": exit_code == 0,
        },
        evidence_payload={
            "exit_code": exit_code,
            "observations": source_shutdown,
            "stderr_path": "source-api-stderr.log",
        },
        evidence_dir=evidence,
        secret=token,
        facts={
            "exit_codes": [exit_code],
            "http_statuses": [],
            "response_facts": {"terminal_health": p_terminal},
            "object_ids": record["canonical_ids"],
            "workspace": record["workspace"],
            "revision_status": record["revisions"],
            "database_evidence": ["shutdown.log"],
            "spy_evidence": ["shutdown.log"],
        },
    )

    _finish_scenario(
        record,
        "Q",
        started_at=q_started,
        entrypoints=["independent partial-start-probe subprocess"],
        actuals={
            "external repeated shutdown": q_probe["double_shutdown_completed"],
            "double scheduler shutdown": q_probe["double_scheduler_shutdown_completed"],
            "partial startup failure": "injected partial-start failure" in q_probe["start_error"],
            "rollback order": (
                "event_bus_stop_after" in q_order
                and "database_close_after" in q_order
                and q_order.index("event_bus_stop_after")
                < q_order.index("database_close_after")
            ),
            "event bus stopped": q_probe["event_bus_stopped"],
            "tasks cleaned": (
                q_probe["failed_tasks_clean"] and q_probe["healthy_tasks_clean"]
            ),
            "connections zero": (
                q_probe["failed_connections"] == 0
                and q_probe["healthy_connections"] == 0
            ),
            "failed container cannot restart": bool(q_probe["restart_error"]),
            "no duplicate execution": q_scheduler_after == q_before_scheduler,
        },
        evidence_payload={
            "probe": q_probe,
            "shutdown_observations": q_new_shutdown,
            "event_counts": [q_before_events, q_events_after],
            "scheduler_counts": [q_before_scheduler, q_scheduler_after],
        },
        evidence_dir=evidence,
        secret=token,
        facts=_scenario_facts(
            record,
            http_start=len(record["http_operations"]),
            command_start=q_command_start,
            response_facts=q_probe,
            object_ids=[],
            workspace=record["workspace"],
            revision_status=[],
            database_evidence=["partial-start-probe.json"],
            spy_evidence=["shutdown.log", "events.log"],
        ),
    )

    n_started = datetime.now(UTC).isoformat()
    event_records = _read_json_lines(spy_root / "events.log")
    record["event_bus"] = event_records
    event_fields = {"topic", "event_type", "payload", "workspace", "trace_id", "timestamp"}
    _finish_scenario(
        record,
        "N",
        started_at=n_started,
        entrypoints=["EventBus spy", "partial-start publish-after-stop probe"],
        actuals={
            "read hint emit no mutation event": (
                f_event_before == f_event_after
                and j_event_before == j_event_after
            ),
            "mutations emit existing events": bool(event_records),
            "event workspace trace persisted": all(
                event_fields <= set(item)
                and item["workspace"]
                and item["trace_id"]
                for item in event_records
            ),
            "publish after stop fails closed": bool(q_probe["publish_after_stop_error"]),
        },
        evidence_payload={
            "events": event_records,
            "read_hint_counts": [f_event_before, f_event_after, j_event_before, j_event_after],
            "publish_after_stop_error": q_probe["publish_after_stop_error"],
        },
        evidence_dir=evidence,
        secret=token,
        facts={
            "exit_codes": [],
            "http_statuses": [],
            "response_facts": {"event_count": len(event_records)},
            "object_ids": record["canonical_ids"],
            "workspace": record["workspace"],
            "revision_status": record["revisions"],
            "database_evidence": [],
            "spy_evidence": ["events.log", "partial-start-probe.json"],
        },
    )

    r_started = datetime.now(UTC).isoformat()
    r_http_start = len(record["http_operations"])
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
        _, restarted_reminder = _http(
            args,
            record,
            "GET",
            f"/reminders/{reminder['id']}/status",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_waiting = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_history = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}/events",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_inbox = _http(
            args,
            record,
            "GET",
            f"/inbox/{inbox['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_work_log = _http(
            args,
            record,
            "GET",
            f"/work-logs/{work_log['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_today = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, restarted_yesterday = _http(
            args,
            record,
            "GET",
            "/daily-review?date=yesterday",
            token=token,
            headers=workspace_headers,
        )
        restarted_sqlite = _evidence_snapshot(
            data_root=source,
            evidence=evidence,
            label="restart-state-sqlite",
            secret=token,
        )
        restarted_state = {
            "task": restarted_task,
            "reminder": restarted_reminder,
            "waiting": restarted_waiting,
            "waiting_history": restarted_history,
            "inbox": restarted_inbox,
            "work_log": restarted_work_log,
            "agenda": _without_volatile(restarted_agenda),
            "today": _normalized_review(restarted_today),
            "yesterday": _normalized_review(restarted_yesterday),
            "sqlite": restarted_sqlite["value"]["sqlite"],
        }
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
    _finish_scenario(
        record,
        "R",
        started_at=r_started,
        entrypoints=["new Uvicorn process on same absolute profile", "API", "SQLite"],
        actuals={
            "user task restart": restarted_state["task"] == source_state["task"],
            "reminder restart": restarted_state["reminder"] == source_state["reminder"],
            "scheduler job run restart": restarted_state["sqlite"] == source_state["sqlite"],
            "claim occurrence restart": restarted_state["sqlite"] == source_state["sqlite"],
            "inbox saga restart": restarted_state["inbox"] == source_state["inbox"],
            "waiting history restart": (
                restarted_state["waiting"] == source_state["waiting"]
                and restarted_state["waiting_history"] == source_state["waiting_history"]
            ),
            "work log restart": restarted_state["work_log"] == source_state["work_log"],
            "agenda restart": restarted_state["agenda"] == source_state["agenda"],
            "today review restart": restarted_state["today"] == source_state["today"],
            "yesterday review restart": (
                restarted_state["yesterday"] == source_state["yesterday"]
            ),
        },
        evidence_payload={
            "source_state_path": source_state_path,
            "restart_state": restarted_state,
            "restart_sqlite_path": restarted_sqlite["path"],
        },
        evidence_dir=evidence,
        secret=token,
        facts=_scenario_facts(
            record,
            http_start=r_http_start,
            command_start=len(record["commands"]),
            response_facts={"comparison": "source == same-root restart"},
            object_ids=record["canonical_ids"],
            workspace=record["workspace"],
            revision_status=record["revisions"],
            database_evidence=[source_sqlite["path"], restarted_sqlite["path"]],
            spy_evidence=["shutdown.log"],
        ),
    )

    s_started = datetime.now(UTC).isoformat()
    before = file_manifest(source)
    record["source_manifest_before_restore"] = before
    restore.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, restore, dirs_exist_ok=True)
    record["restore_manifest"] = file_manifest(restore)
    _finish_scenario(
        record,
        "S",
        started_at=s_started,
        entrypoints=["static filesystem copy after P/Q"],
        actuals={
            "shutdown gates passed before copy": (
                record["scenarios"]["P"]["result"] == "PASS"
                and record["scenarios"]["Q"]["result"] == "PASS"
            ),
            "complete file inventory": before == record["restore_manifest"],
            "size and sha256": all(
                item["size"] >= 0 and len(str(item["sha256"])) == 64 for item in before
            ),
            "no product process during copy": (
                process.poll() is not None and restarted.poll() is not None
            ),
        },
        evidence_payload={
            "source_manifest": before,
            "restore_manifest": record["restore_manifest"],
            "process_exit_codes": [process.returncode, restarted.returncode],
        },
        evidence_dir=evidence,
        secret=token,
        facts={
            "exit_codes": [process.returncode, restarted.returncode],
            "http_statuses": [],
            "response_facts": {"file_count": len(before)},
            "object_ids": record["canonical_ids"],
            "workspace": record["workspace"],
            "revision_status": record["revisions"],
            "database_evidence": [item["path"] for item in before],
            "spy_evidence": ["shutdown.log"],
        },
    )

    t_started = datetime.now(UTC).isoformat()
    checkout_data_before = file_manifest(repo / "data")
    source_before_restore_run = file_manifest(source)
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
        u_started = datetime.now(UTC).isoformat()
        u_http_start = len(record["http_operations"])
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
        _, restored_reminder = _http(
            args,
            record,
            "GET",
            f"/reminders/{reminder['id']}/status",
            token=token,
            headers=workspace_headers,
        )
        _, restored_waiting = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restored_history = _http(
            args,
            record,
            "GET",
            f"/waiting-for/{waiting['item']['id']}/events",
            token=token,
            headers=workspace_headers,
        )
        _, restored_inbox = _http(
            args,
            record,
            "GET",
            f"/inbox/{inbox['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restored_work_log = _http(
            args,
            record,
            "GET",
            f"/work-logs/{work_log['id']}",
            token=token,
            headers=workspace_headers,
        )
        _, restored_agenda = _http(
            args,
            record,
            "GET",
            "/agenda",
            token=token,
            headers=workspace_headers,
        )
        _, restored_today = _http(
            args,
            record,
            "GET",
            "/daily-review?date=today",
            token=token,
            headers=workspace_headers,
        )
        _, restored_yesterday = _http(
            args,
            record,
            "GET",
            "/daily-review?date=yesterday",
            token=token,
            headers=workspace_headers,
        )
        restored_sqlite = _evidence_snapshot(
            data_root=restore,
            evidence=evidence,
            label="restore-state-sqlite",
            secret=token,
        )
        restored_state = {
            "task": restored_task,
            "reminder": restored_reminder,
            "waiting": restored_waiting,
            "waiting_history": restored_history,
            "inbox": restored_inbox,
            "work_log": restored_work_log,
            "agenda": _without_volatile(restored_agenda),
            "today": _normalized_review(restored_today),
            "yesterday": _normalized_review(restored_yesterday),
            "sqlite": restored_sqlite["value"]["sqlite"],
        }
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
    _finish_scenario(
        record,
        "T",
        started_at=t_started,
        entrypoints=["isolated absolute restore profile", "filesystem manifests"],
        actuals={
            "independent absolute profile": (
                Path(restore_env["AI_LAB_DATA_DIR"]).is_absolute()
                and Path(restore_env["AI_LAB_DATA_DIR"]) == restore
                and restore != source
            ),
            "source root not accessed": source_before_restore_run == after,
            "checkout data not accessed": (
                checkout_data_before == file_manifest(repo / "data")
            ),
            "source hashes unchanged": before == after,
        },
        evidence_payload={
            "source_before": source_before_restore_run,
            "source_after": after,
            "checkout_before": checkout_data_before,
            "checkout_after": file_manifest(repo / "data"),
            "restore_profile": {
                "data_root": restore_env["AI_LAB_DATA_DIR"],
                "sqlite_root": restore_env["AI_LAB_SQLITE_DIR"],
            },
        },
        evidence_dir=evidence,
        secret=token,
        facts={
            "exit_codes": [restored_exit],
            "http_statuses": [],
            "response_facts": {"restore_root": str(restore)},
            "object_ids": record["canonical_ids"],
            "workspace": record["workspace"],
            "revision_status": record["revisions"],
            "database_evidence": [item["path"] for item in before],
            "spy_evidence": ["shutdown.log"],
        },
    )
    source_without_appended = source_state
    restore_without_append = restored_state
    comparison = {
        key: restore_without_append[key] == source_without_appended[key]
        for key in source_without_appended
    }
    record["source_restore_comparison"] = comparison
    _finish_scenario(
        record,
        "U",
        started_at=u_started,
        entrypoints=["restore API", "SQLite", "post-restore Work Log append"],
        actuals={
            "canonical ids equal": all(
                canonical_id in json.dumps(restored_state, ensure_ascii=False)
                for canonical_id in (
                    source_state["task"]["id"],
                    source_state["reminder"]["reminder_id"],
                    source_state["waiting"]["id"],
                    source_state["inbox"]["id"],
                    source_state["work_log"]["id"],
                )
            ),
            "revision status equal": (
                restored_state["task"] == source_state["task"]
                and restored_state["reminder"] == source_state["reminder"]
            ),
            "history equal": restored_state["waiting_history"] == source_state["waiting_history"],
            "jobs runs equal": restored_state["sqlite"] == source_state["sqlite"],
            "claims saga equal": restored_state["inbox"] == source_state["inbox"],
            "agenda equal": restored_state["agenda"] == source_state["agenda"],
            "today review equal": restored_state["today"] == source_state["today"],
            "yesterday review equal": (
                restored_state["yesterday"] == source_state["yesterday"]
            ),
            "restore append leaves source unchanged": before == after,
        },
        evidence_payload={
            "source_state_path": source_state_path,
            "restore_state": restored_state,
            "comparison": comparison,
            "appended_work_log": appended,
        },
        evidence_dir=evidence,
        secret=token,
        facts=_scenario_facts(
            record,
            http_start=u_http_start,
            command_start=len(record["commands"]),
            response_facts={"comparison": comparison, "appended_id": appended["id"]},
            object_ids=record["canonical_ids"],
            workspace=record["workspace"],
            revision_status=record["revisions"],
            database_evidence=[source_sqlite["path"], restored_sqlite["path"]],
            spy_evidence=["shutdown.log"],
        ),
    )

    v_started = datetime.now(UTC).isoformat()
    v_http_start = len(record["http_operations"])
    date_failure_status, date_failure = _http(
        args,
        record,
        "GET",
        "/daily-review?date=invalid",
        token=token,
        headers=workspace_headers,
        expected=(400,),
    )
    not_found_status, not_found = _http(
        args,
        record,
        "GET",
        "/tasks/ut_missing",
        token=token,
        headers=workspace_headers,
        expected=(404,),
    )
    observed_failures = {
        "auth": missing_auth,
        "workspace": cross_mutation,
        "date_query": date_failure,
        "not_found": not_found,
        "stale_revision": stale_active,
        "unsupported_state": h_unsupported,
    }
    record["failure_info_checks"] = [
        {
            "kind": name,
            "failure": _safe(_failure_payload(value), secret=token),
            "complete": _failure_is_complete(value, secret=token),
        }
        for name, value in observed_failures.items()
    ]
    config_failure_records = [
        {
            **value,
            "stderr": (evidence / str(value["stderr_path"])).read_text(
                encoding="utf-8",
                errors="replace",
            ),
        }
        for value in negative_profiles.values()
    ]
    config_failures_complete = all(
        item["exit_code"] != 0 and bool(item["stderr"].strip())
        for item in config_failure_records
    )
    _finish_scenario(
        record,
        "V",
        started_at=v_started,
        entrypoints=[
            "profile validation subprocesses",
            "API FailureInfo responses",
            "Reminder idempotency replay",
            "Inbox Saga replay",
        ],
        actuals={
            "config failure info": config_failures_complete,
            "auth failure info": _failure_is_complete(missing_auth, secret=token),
            "workspace failure info": _failure_is_complete(cross_mutation, secret=token),
            "date query failure info": (
                date_failure_status == 400
                and _failure_is_complete(date_failure, secret=token)
            ),
            "not found failure info": (
                not_found_status == 404
                and _failure_is_complete(not_found, secret=token)
            ),
            "stale revision failure info": _failure_is_complete(stale_active, secret=token),
            "unsupported state failure info": _failure_is_complete(h_unsupported, secret=token),
            "dependency scheduler failure info": bool(q_probe["start_error"]),
            "shutdown restore failure info": (
                bool(q_probe["publish_after_stop_error"]) and restored_exit == 0
            ),
            "failure fields secret safe": all(
                item["complete"] for item in record["failure_info_checks"]
            ),
            "idempotency and saga replay": (
                reminder_replayed == reminder_keyed
                and replayed_inbox.get("resolved_target_id") == target_id
            ),
        },
        evidence_payload={
            "failures": record["failure_info_checks"],
            "config_failures": config_failure_records,
            "reminder_replay": [reminder_keyed, reminder_replayed],
            "inbox_replay": [resolved_inbox, replayed_inbox],
            "shutdown_probe": q_probe,
        },
        evidence_dir=evidence,
        secret=token,
        facts=_scenario_facts(
            record,
            http_start=v_http_start,
            command_start=len(record["commands"]),
            response_facts={
                "date_status": date_failure_status,
                "not_found_status": not_found_status,
            },
            object_ids=[reminder["id"], inbox["id"], target_id],
            workspace=record["workspace"],
            revision_status=record["revisions"],
            database_evidence=[source_sqlite["path"], restored_sqlite["path"]],
            spy_evidence=["events.log", "shutdown.log", "partial-start-probe.json"],
        ),
    )
    calls = len(counter.read_text(encoding="utf-8").splitlines())
    record["provider_spy_call_count"] = calls
    events_path = spy_root / "events.log"
    scheduler_path = spy_root / "scheduler.log"
    record["event_bus"] = _read_json_lines(events_path)
    record["scheduler_mutations"] = _read_json_lines(scheduler_path)
    if calls != 0:
        raise ProductAcceptanceError(f"provider spy recorded {calls} calls")
    l_started = datetime.now(UTC).isoformat()
    _finish_scenario(
        record,
        "L",
        started_at=l_started,
        entrypoints=["provider spy across startup/read/hint/mutation/restart/restore"],
        actuals={
            "provider spy installed": record["provider_spy_installed"] is True,
            "provider calls zero": calls == 0,
        },
        evidence_payload={
            "counter_path": counter.name,
            "call_count": calls,
            "covered_processes": [
                record["api_pid"],
                record["restart_api_pid"],
                record["restore_api_pid"],
            ],
        },
        evidence_dir=evidence,
        secret=token,
        facts={
            "exit_codes": [exit_code, restart_exit, restored_exit],
            "http_statuses": [],
            "response_facts": {"provider_calls": calls},
            "object_ids": record["canonical_ids"],
            "workspace": record["workspace"],
            "revision_status": record["revisions"],
            "database_evidence": [],
            "spy_evidence": [counter.name],
        },
    )
    for path in evidence.rglob("*"):
        if path.is_file() and token in path.read_text(
            encoding="utf-8",
            errors="ignore",
        ):
            raise ProductAcceptanceError(
                f"secret leaked into evidence: {path.name}"
            )
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
    record: dict[str, Any] = {}
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
    except ProductAcceptanceError as exc:
        if manifest_path.parent.exists():
            try:
                current = record or (
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
    except Exception as exc:  # noqa: BLE001 - harness boundary
        if manifest_path.parent.exists():
            try:
                current = record or (
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest_path.exists()
                    else {}
                )
                current.update({
                    "status": HARNESS_FAILURE,
                    "failure_type": type(exc).__name__,
                    "failure": str(exc),
                })
                _write_manifest(manifest_path, current)
            except Exception:  # noqa: BLE001, S110 - preserve primary failure
                pass
        print(f"{HARNESS_FAILURE}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
