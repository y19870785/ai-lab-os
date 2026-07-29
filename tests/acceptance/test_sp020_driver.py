"""ACC-020 driver preparation tests; these do not execute formal acceptance."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DRIVER = Path(__file__).parents[2] / "scripts" / "acceptance" / "sp020_driver.py"


def test_prepare_only_writes_auditable_manifest(tmp_path: Path) -> None:
    source = (tmp_path / "source").resolve()
    restore = (tmp_path / "restore").resolve()
    evidence = tmp_path / "evidence"
    source.mkdir()
    (source / "state.sqlite3").write_bytes(b"sqlite-evidence")

    result = subprocess.run(
        [
            sys.executable,
            str(DRIVER),
            "--frozen-head",
            "not-yet-frozen",
            "--source-data-root",
            str(source),
            "--restore-data-root",
            str(restore),
            "--evidence-dir",
            str(evidence),
            "--prepare-only",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PREPARED_NOT_EXECUTED"
    assert manifest["frozen_head"] == "not-yet-frozen"
    assert len(manifest["driver_sha256"]) == 64
    assert manifest["source_data_root"] == str(source)
    assert manifest["restore_data_root"] == str(restore)
    assert manifest["sqlite_files"][0]["sha256"]
    assert manifest["commands"] == []
    assert manifest["provider_spy_call_count"] == 0


def test_driver_rejects_same_source_and_restore_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(DRIVER),
            "--frozen-head",
            "not-yet-frozen",
            "--source-data-root",
            str(root),
            "--restore-data-root",
            str(root),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--prepare-only",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert "INVALID_ACCEPTANCE_HARNESS" in result.stderr
