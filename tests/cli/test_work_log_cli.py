"""Real-process Work Log CLI contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _run(tmp_path, *args):
    environment = os.environ.copy()
    environment.update(
        {
            "AI_LAB_PROVIDER_MODE": "test",
            "AI_LAB_DATA_DIR": str(tmp_path),
            "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
            "AI_LAB_API_AUTH_ENABLED": "false",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=os.getcwd(),
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def test_work_log_create_list_show_json_and_workspace(tmp_path):
    created = _run(
        tmp_path,
        "work-log",
        "create",
        "完成 CLI 验收",
        "--workspace-id",
        "alpha",
        "--tag",
        "CLI",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    record = json.loads(created.stdout)
    assert record["id"].startswith("wl_")
    assert record["source"] == "cli"

    listing = _run(
        tmp_path,
        "work-log",
        "list",
        "--workspace-id",
        "alpha",
        "--tag",
        "CLI",
        "--limit",
        "1",
        "--json",
    )
    assert listing.returncode == 0, listing.stderr
    assert json.loads(listing.stdout)["items"][0]["id"] == record["id"]

    hidden = _run(
        tmp_path,
        "work-log",
        "list",
        "--workspace-id",
        "beta",
        "--json",
    )
    assert json.loads(hidden.stdout)["items"] == []

    shown = _run(
        tmp_path,
        "work-log",
        "show",
        record["id"],
        "--workspace-id",
        "alpha",
        "--json",
    )
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["id"] == record["id"]


def test_legacy_log_alias_and_failure_exit_code(tmp_path):
    created = _run(tmp_path, "log", "兼容 CLI 记录")
    assert created.returncode == 0, created.stderr
    assert "[OK] wl_" in created.stdout

    invalid = _run(tmp_path, "work-log", "show", "raw-memory-id")
    assert invalid.returncode == 2
    assert "work_log.id_invalid" in invalid.stderr
