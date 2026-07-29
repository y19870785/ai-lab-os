"""ACC-020 driver harness tests; these never execute formal acceptance."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
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
    command = [
        sys.executable,
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


def test_harness_and_product_failures_are_distinct():
    assert not issubclass(driver.HarnessError, driver.ProductAcceptanceError)
    assert driver.HARNESS_FAILURE != driver.PRODUCT_FAILURE


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
