"""ACC-020 driver harness tests; these never execute formal acceptance."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DRIVER = Path(__file__).parents[2] / "scripts" / "acceptance" / "sp020_driver.py"
SPEC = importlib.util.spec_from_file_location("sp020_driver_under_test", DRIVER)
assert SPEC and SPEC.loader
driver = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = driver
SPEC.loader.exec_module(driver)


def _driver_hash() -> str:
    return hashlib.sha256(DRIVER.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def _clean_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "acc020@example.invalid")
    _git(repo, "config", "user.name", "ACC-020")
    (repo / "marker.txt").write_text("clean", encoding="utf-8")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", "fixture")
    return repo.resolve(), _git(repo, "rev-parse", "HEAD")


def _run(
    tmp_path: Path,
    monkeypatch,
    *,
    repo: Path | None = None,
    head: str | None = None,
    source: Path | None = None,
    restore: Path | None = None,
    evidence: Path | None = None,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    repo, actual_head = (repo, head) if repo and head else _clean_repo(tmp_path)
    source = (source or (tmp_path / "source")).resolve()
    restore = (restore or (tmp_path / "restore")).resolve()
    evidence = (evidence or (tmp_path / "evidence")).resolve()
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
    monkeypatch.setenv("AI_LAB_API_TOKEN", "test-token")
    harness_entry = (
        "import importlib.util,sys;"
        "path=sys.argv.pop(1);"
        "spec=importlib.util.spec_from_file_location("
        "'sp020_driver_harness_test',path);"
        "module=importlib.util.module_from_spec(spec);"
        "sys.modules[spec.name]=module;"
        "spec.loader.exec_module(module);"
        "module._is_windows=lambda:True;"
        "raise SystemExit(module.main())"
    )
    command = [
        sys.executable,
        "-c",
        harness_entry,
        str(DRIVER),
        "--frozen-head",
        actual_head,
        "--expected-driver-sha256",
        _driver_hash(),
        "--repository-root",
        str(repo),
        "--source-data-root",
        str(source),
        "--restore-data-root",
        str(restore),
        "--evidence-dir",
        str(evidence),
        "--api-port",
        str(_free_port()),
        "--prepare-only",
        *(extra or []),
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_real_driver_platform_gate_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(driver, "_is_windows", lambda: False)
    with pytest.raises(driver.HarnessError, match="ACC-020 requires Windows"):
        driver.validate_harness(SimpleNamespace(), DRIVER)


def test_prepare_only_writes_unmeasured_a_to_v_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result = _run(tmp_path, monkeypatch)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(
        (tmp_path / "evidence" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "acc-020-evidence-v1"
    assert manifest["status"] == "PREPARED_NOT_EXECUTED"
    assert manifest["commands"] == []
    assert manifest["provider_spy_call_count"] is None
    assert manifest["provider_spy_installed"] is False
    assert tuple(manifest["scenarios"]) == tuple("ABCDEFGHIJKLMNOPQRSTUV")
    assert {
        value["result"] for value in manifest["scenarios"].values()
    } == {"NOT_MEASURED"}
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "test-token" not in serialized
    assert "test-token" not in result.stdout
    assert "test-token" not in result.stderr


@pytest.mark.parametrize("relation", ["same", "source_contains", "restore_contains"])
def test_driver_rejects_same_or_nested_roots(tmp_path, monkeypatch, relation):
    if relation == "same":
        source = restore = (tmp_path / "data").resolve()
    elif relation == "source_contains":
        source = (tmp_path / "data").resolve()
        restore = (source / "restore").resolve()
    else:
        restore = (tmp_path / "data").resolve()
        source = (restore / "source").resolve()
    result = _run(
        tmp_path,
        monkeypatch,
        source=source,
        restore=restore,
    )
    assert result.returncode == 2
    assert "INVALID_ACCEPTANCE_HARNESS" in result.stderr


def test_driver_rejects_checkout_default_data_root(tmp_path, monkeypatch):
    repo, head = _clean_repo(tmp_path)
    result = _run(
        tmp_path,
        monkeypatch,
        repo=repo,
        head=head,
        source=repo / "data",
    )
    assert result.returncode == 2
    assert "checkout default data directory" in result.stderr


def test_driver_rejects_nonempty_restore_root(tmp_path, monkeypatch):
    restore = tmp_path / "restore"
    restore.mkdir()
    (restore / "old.sqlite3").write_bytes(b"old")
    result = _run(
        tmp_path,
        monkeypatch,
        restore=restore.resolve(),
    )
    assert result.returncode == 2
    assert "restore data root must be empty" in result.stderr


def test_driver_rejects_dirty_tree(tmp_path, monkeypatch):
    repo, head = _clean_repo(tmp_path)
    (repo / "marker.txt").write_text("dirty", encoding="utf-8")
    result = _run(tmp_path, monkeypatch, repo=repo, head=head)
    assert result.returncode == 2
    assert "working tree must be clean" in result.stderr


def test_driver_rejects_head_and_driver_hash_mismatch(tmp_path, monkeypatch):
    repo, head = _clean_repo(tmp_path)
    result = _run(
        tmp_path,
        monkeypatch,
        repo=repo,
        head="0" * 40,
    )
    assert result.returncode == 2
    assert "frozen Head mismatch" in result.stderr

    args = SimpleNamespace(
        repository_root=repo,
        frozen_head=head,
        expected_driver_sha256="0" * 64,
        source_data_root=(tmp_path / "source").resolve(),
        restore_data_root=(tmp_path / "restore").resolve(),
        evidence_dir=(tmp_path / "evidence").resolve(),
        api_port=_free_port(),
    )
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
    monkeypatch.setenv("AI_LAB_API_TOKEN", "token")
    monkeypatch.setattr(driver, "_is_windows", lambda: True)
    with pytest.raises(driver.HarnessError, match="driver SHA-256 mismatch"):
        driver.validate_harness(args, DRIVER)


def test_driver_rejects_missing_secret(tmp_path, monkeypatch):
    repo, head = _clean_repo(tmp_path)
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
    monkeypatch.delenv("AI_LAB_API_TOKEN", raising=False)
    args = SimpleNamespace(
        repository_root=repo,
        frozen_head=head,
        expected_driver_sha256=_driver_hash(),
        source_data_root=(tmp_path / "source").resolve(),
        restore_data_root=(tmp_path / "restore").resolve(),
        evidence_dir=(tmp_path / "evidence").resolve(),
        api_port=_free_port(),
    )
    monkeypatch.setattr(driver, "_is_windows", lambda: True)
    with pytest.raises(driver.HarnessError, match="API token"):
        driver.validate_harness(args, DRIVER)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_command_failure_is_recorded_and_terminates(tmp_path):
    records = []
    with pytest.raises(driver.ProductAcceptanceError):
        driver.run_command(
            [sys.executable, "-c", "raise SystemExit(7)"],
            env=dict(os.environ),
            cwd=tmp_path,
            records=records,
        )
    assert records[0]["exit_code"] == 7
    assert records[0]["finished_at"]


def test_manifest_file_schema_and_hashes(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "state.sqlite3").write_bytes(b"sqlite-evidence")
    manifest = driver.file_manifest(root)
    assert manifest == [{
        "path": "state.sqlite3",
        "size": len(b"sqlite-evidence"),
        "sha256": hashlib.sha256(b"sqlite-evidence").hexdigest(),
    }]


def test_sqlite_snapshot_uses_column_names(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    database = root / "state.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE facts (id TEXT, revision INTEGER)")
        connection.execute("INSERT INTO facts VALUES ('ut_example', 3)")
    assert driver.sqlite_snapshot(root)["state.sqlite3"]["tables"]["facts"] == [
        {"id": "ut_example", "revision": 3}
    ]


def test_harness_and_product_failures_are_distinct():
    assert not issubclass(driver.HarnessError, driver.ProductAcceptanceError)
    assert driver.HARNESS_FAILURE != driver.PRODUCT_FAILURE


def _scenario_facts() -> dict[str, object]:
    return {
        "exit_codes": [0],
        "http_statuses": [{"method": "GET", "path": "/health", "status": 200}],
        "response_facts": {"status": "ok"},
        "object_ids": ["ut_example"],
        "workspace": {"tenant_id": "tenant-a", "workspace_id": "workspace-a"},
        "revision_status": [{"id": "ut_example", "revision": 1, "status": "active"}],
        "database_evidence": ["sqlite-snapshot.json"],
        "spy_evidence": ["events.log"],
    }


def test_scenario_missing_required_check_cannot_pass(tmp_path):
    with pytest.raises(driver.ProductAcceptanceError, match="missing required checks"):
        driver._record_scenario(
            {},
            "L",
            started_at="2026-01-01T00:00:00Z",
            entrypoints=["provider spy"],
            checks=[],
            facts=_scenario_facts(),
            evidence_dir=tmp_path,
        )


def test_any_failed_check_marks_scenario_fail(tmp_path):
    record = {"scenarios": {}}
    checks = [
        driver._check(
            "provider spy installed",
            expected=True,
            actual=True,
            evidence_path="provider.json",
        ),
        driver._check(
            "provider calls zero",
            expected=True,
            actual=False,
            evidence_path="provider.json",
        ),
    ]
    with pytest.raises(driver.ProductAcceptanceError, match="failed checks"):
        driver._record_scenario(
            record,
            "L",
            started_at="2026-01-01T00:00:00Z",
            entrypoints=["provider spy"],
            checks=checks,
            facts=_scenario_facts(),
            evidence_dir=tmp_path,
        )
    assert record["scenarios"]["L"]["result"] == "FAIL"


def test_manual_pass_helper_cannot_bypass_assertions():
    source = DRIVER.read_text(encoding="utf-8")
    assert not hasattr(driver, "_pass")
    assert "_pass(" not in source


def test_driver_records_real_shutdown_and_partial_start_evidence():
    source = DRIVER.read_text(encoding="utf-8")
    assert "connection_counts.append(0)" not in source
    assert "_partial_start_probe(" in source
    assert "partial-start-probe.json" in source
    assert "database_close_after" in source


def test_driver_requires_api_cli_and_ceo_scenario_evidence():
    source = DRIVER.read_text(encoding="utf-8")
    assert '"/daily-review?date=today"' in source
    assert '"/daily-review?date=yesterday"' in source
    assert source.count('"daily-review",') >= 2
    assert '"CEO Assistant /tasks and canonical mutation with Workspace B"' in source
    assert "k-ceo-list-isolated" in source
    assert "k-ceo-mutation-isolated" in source


def test_driver_requires_event_and_source_restore_comparisons():
    source = DRIVER.read_text(encoding="utf-8")
    for field in ("topic", "event_type", "payload", "workspace", "trace_id", "timestamp"):
        assert field in source
    for key in (
        "task",
        "reminder",
        "waiting_history",
        "inbox",
        "work_log",
        "agenda",
        "today",
        "yesterday",
        "sqlite",
    ):
        assert f'"{key}"' in source
    assert "failure_info_checks" in source
    assert "reminder_replayed == reminder_keyed" in source
    assert "replayed_inbox.get(\"resolved_target_id\") == target_id" in source


def test_safe_evidence_redacts_tokens_and_secret_values():
    secret = "acc020-super-secret"
    safe = driver._safe(
        {
            "authorization": f"Bearer {secret}",
            "nested": {"api_token": secret, "message": f"value={secret}"},
        },
        secret=secret,
    )
    serialized = json.dumps(safe)
    assert secret not in serialized
    assert serialized.count("[REDACTED]") >= 3


def _complete_failure() -> dict[str, object]:
    return {
        "code": "component.operation.failed",
        "category": "dependency_failure",
        "component": "component",
        "operation": "operation",
        "trace_id": "trace_acc020",
        "retryable": False,
        "details": {"probe": "acc020"},
    }


def _complete_config_failures() -> dict[str, dict[str, object]]:
    return {
        name: {"exit_code": 2, "failure": _complete_failure()}
        for name in (
            "invalid timezone",
            "invalid provider",
            "missing auth token",
            "relative data root",
            "relative sqlite root",
            "sqlite outside data root",
            "unknown profile",
        )
    }


def test_config_failure_traceback_cannot_pass_scenario_v():
    records = _complete_config_failures()
    records["invalid timezone"]["failure"] = {
        "unparseable_stderr": "Traceback (most recent call last): ValueError"
    }
    assessed = driver._config_failure_assessment(records, secret="token")
    assert assessed["complete"] is False
    assert assessed["cases"]["invalid timezone"]["complete"] is False


@pytest.mark.parametrize(
    "missing",
    (
        "code",
        "category",
        "component",
        "operation",
        "trace_id",
        "retryable",
        "details",
    ),
)
def test_missing_failure_info_field_cannot_pass_scenario_v(missing):
    failure = _complete_failure()
    failure.pop(missing)
    assessed = driver._failure_assessment(failure)
    assert assessed["complete"] is False
    assert missing in assessed["missing"]


@pytest.mark.parametrize("kind", ("dependency", "shutdown", "restore"))
def test_plain_error_string_cannot_satisfy_scenario_v(kind):
    assessed = driver._failure_assessment(f"{kind} failed")
    assert assessed["complete"] is False
    assert assessed["failure"] == {}


def _complete_q_probe() -> dict[str, object]:
    call = {
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "exception": None,
        "lifecycle_before": "ready",
        "lifecycle_after": "stopped",
        "background_tasks": 0,
        "connection_count": 0,
        "job_count": 1,
        "run_count": 1,
        "occurrence_count": 1,
    }
    persisted = {
        "execution_count": 1,
        "jobs": [{"id": "job_q"}],
        "runs": [{"id": "run_q", "job_id": "job_q"}],
        "occurrences": [{"id": "occ_q", "reminder_id": "rem_q"}],
        "business_event_count": 2,
    }
    return {
        "job_evidence": {
            "job_id": "job_q",
            "reminder_id": "rem_q",
            "before_shutdown": persisted,
            "after_shutdown": dict(persisted),
        },
        "scheduler_shutdown_calls": [dict(call), dict(call)],
        "container_shutdown_calls": [dict(call), dict(call)],
        "partial_start": {
            "failure": _complete_failure(),
            "restart_failure": _complete_failure(),
            "lifecycle": "failed",
            "rollback_order_valid": True,
            "event_bus_stopped": True,
            "background_tasks": 0,
            "connection_count": 0,
        },
        "final_background_tasks": 0,
        "final_connection_count": 0,
    }


def test_q_requires_nonempty_real_job_run_and_occurrence():
    probe = _complete_q_probe()
    probe["job_evidence"]["before_shutdown"]["runs"] = []
    assert driver._q_probe_assessment(probe)["no duplicate execution"] is False


def test_q_rejects_execution_count_increasing_from_one_to_two():
    probe = _complete_q_probe()
    probe["job_evidence"]["after_shutdown"] = {
        **probe["job_evidence"]["after_shutdown"],
        "execution_count": 2,
        "runs": [
            {"id": "run_q", "job_id": "job_q"},
            {"id": "run_q_2", "job_id": "job_q"},
        ],
    }
    assert driver._q_probe_assessment(probe)["no duplicate execution"] is False


def test_q_completed_flags_cannot_replace_observed_calls():
    probe = _complete_q_probe()
    probe["scheduler_shutdown_calls"] = []
    probe["container_shutdown_calls"] = []
    probe["double_shutdown_completed"] = True
    probe["double_scheduler_shutdown_completed"] = True
    assessed = driver._q_probe_assessment(probe)
    assert assessed["external repeated shutdown"] is False
    assert assessed["double scheduler shutdown"] is False


def test_k_title_leak_fails_even_when_id_is_hidden():
    model = {
        "protected_values": ["ut_secret", "Workspace A unique title"],
        "primary_ids": ["ut_secret"],
        "agenda_ids": [],
        "review_ids": [],
        "cli_ids": [],
        "hint_ids": [],
        "task_status": 404,
        "api_mutation_status": 404,
        "workspace_b_task_count": 0,
        "workspace_b_task_ids": [],
        "ceo_list_output": "Workspace A unique title",
        "ceo_mutation_output": "[错误] not found",
        "ceo_mutation_attempted": True,
        "ceo_mutation_blocked": True,
        "source_before": {"revision": 1, "status": "active"},
        "source_after": {"revision": 1, "status": "active"},
        "workspace_id": "isolated",
    }
    assert driver._workspace_isolation_assessment(model)["ceo invisible"] is False


def test_scenario_n_excludes_independent_q_probe_workspace_events():
    source = [{"workspace": {"workspace_id": "acc020-workspace"}}]
    q_probe = [{"workspace": {"workspace_id": "q-probe"}}]
    selected = driver._source_event_records(
        source + q_probe,
        probe_start=len(source),
    )
    assert selected == source


def test_scenario_n_distinguishes_persisted_and_failed_event_workspaces():
    def event(topic: str, workspace_id: str, trace_id: str = "trace") -> dict:
        return {
            "topic": topic,
            "event_type": topic,
            "payload": {},
            "workspace": {"workspace_id": workspace_id},
            "trace_id": trace_id,
            "timestamp": "2026-01-01T00:00:00Z",
        }

    assert driver._event_contract_assessment(
        [
            event("user_task.updated", "workspace-a"),
            event("user_task.failed", "isolated"),
        ],
        persisted_workspace_id="workspace-a",
        allowed_failure_workspace_ids={"workspace-a", "isolated"},
    )
    assert not driver._event_contract_assessment(
        [event("user_task.updated", "isolated")],
        persisted_workspace_id="workspace-a",
        allowed_failure_workspace_ids={"workspace-a", "isolated"},
    )
    assert not driver._event_contract_assessment(
        [event("user_task.failed", "isolated", trace_id="")],
        persisted_workspace_id="workspace-a",
        allowed_failure_workspace_ids={"workspace-a", "isolated"},
    )


def test_failure_info_with_token_cannot_pass_scenario_v():
    failure = _complete_failure()
    failure["details"] = {"message": "Bearer acc020-secret-token"}
    assessed = driver._failure_assessment(
        failure,
        secrets=("acc020-secret-token",),
    )
    assert assessed["complete"] is False
    assert assessed["secret_safe"] is False


def test_nonprepare_mode_dispatches_real_execution(monkeypatch, tmp_path):
    evidence = (tmp_path / "evidence").resolve()
    args = SimpleNamespace(
        prepare_only=False,
        rehearsal=True,
        formal=False,
        evidence_dir=evidence,
        frozen_head="f" * 40,
        api_port=_free_port(),
    )
    calls = {"execute": 0}
    monkeypatch.setattr(driver, "parse_args", lambda: args)
    monkeypatch.setattr(
        driver,
        "validate_harness",
        lambda _args, _driver: {
            "driver_sha256": _driver_hash(),
            "source": str((tmp_path / "source").resolve()),
            "restore": str((tmp_path / "restore").resolve()),
            "evidence": str(evidence),
        },
    )

    def execute(_args, record, _path):
        calls["execute"] += 1
        record["status"] = "REHEARSAL_COMPLETE_NOT_FORMAL_ACCEPTANCE"

    monkeypatch.setattr(driver, "_execute", execute)
    assert driver.main() == 0
    assert calls["execute"] == 1


def test_unexpected_driver_exception_is_invalid_harness(monkeypatch, tmp_path):
    evidence = (tmp_path / "evidence").resolve()
    args = SimpleNamespace(
        prepare_only=False,
        rehearsal=True,
        formal=False,
        evidence_dir=evidence,
        frozen_head="f" * 40,
        api_port=_free_port(),
    )
    monkeypatch.setattr(driver, "parse_args", lambda: args)
    monkeypatch.setattr(
        driver,
        "validate_harness",
        lambda _args, _driver: {
            "driver_sha256": _driver_hash(),
            "source": str((tmp_path / "source").resolve()),
            "restore": str((tmp_path / "restore").resolve()),
            "evidence": str(evidence),
        },
    )
    monkeypatch.setattr(
        driver,
        "_execute",
        lambda *_args: (_ for _ in ()).throw(IndexError("driver defect")),
    )
    assert driver.main() == 2
    manifest = json.loads(
        (evidence / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == driver.HARNESS_FAILURE


def test_execute_adds_repository_root_for_runtime_contract_imports(
    monkeypatch,
    tmp_path,
):
    repo = (tmp_path / "repo").resolve()
    repo.mkdir()
    source = (tmp_path / "source").resolve()
    restore = (tmp_path / "restore").resolve()
    evidence = (tmp_path / "evidence").resolve()
    args = SimpleNamespace(
        repository_root=repo,
        source_data_root=source,
        restore_data_root=restore,
        evidence_dir=evidence,
    )
    monkeypatch.setattr(
        driver,
        "_provider_spy",
        lambda _evidence: (_ for _ in ()).throw(RuntimeError("stop after path")),
    )
    monkeypatch.setattr(driver.sys, "path", [
        value for value in sys.path if value != str(repo)
    ])
    with pytest.raises(RuntimeError, match="stop after path"):
        driver._execute(args, {}, evidence / "manifest.json")
    assert driver.sys.path[0] == str(repo)


def test_driver_uses_existing_work_log_http_status_contract():
    source = DRIVER.read_text(encoding="utf-8")
    assert source.count('"POST",\n            "/work-logs"') == 2
    assert source.count("expected=(200,),") >= 2


def test_stop_api_cleans_up_process_on_failure(tmp_path):
    stdout = (tmp_path / "stdout.log").open("w", encoding="utf-8")
    stderr = (tmp_path / "stderr.log").open("w", encoding="utf-8")
    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=stdout,
        stderr=stderr,
        text=True,
        creationflags=creationflags,
    )
    driver._stop_api(process, stdout, stderr)
    assert process.poll() is not None


def test_windows_ctrl_break_exit_requires_shutdown_completion(
    tmp_path, monkeypatch
):
    log = tmp_path / "stderr.log"
    log.write_text(
        "Application shutdown complete.\nFinished server process [42]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(driver.os, "name", "nt")
    driver._assert_graceful_shutdown(
        exit_code=3,
        stderr_path=log,
        label="test",
    )
    log.write_text("abrupt exit", encoding="utf-8")
    with pytest.raises(driver.ProductAcceptanceError):
        driver._assert_graceful_shutdown(
            exit_code=3,
            stderr_path=log,
            label="test",
        )
