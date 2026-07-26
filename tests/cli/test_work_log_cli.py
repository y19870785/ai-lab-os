"""Real-process Work Log CLI contract tests."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest

from core.errors import FailureException
from core.workspace.models import WorkspaceKey

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


@pytest.mark.parametrize(
    ("args", "expected_code"),
    [
        (
            ("work-log", "create", "Invalid", "--timezone", "Mars/Olympus"),
            "work_log.timezone_invalid",
        ),
        (
            (
                "work-log",
                "create",
                "Naive",
                "--occurred-at",
                "2026-07-23T10:00:00",
            ),
            "work_log.occurred_at_invalid",
        ),
        (
            (
                "work-log",
                "list",
                "--date-from",
                "2026-07-24T00:00:00Z",
                "--date-to",
                "2026-07-23T00:00:00Z",
            ),
            "work_log.query_invalid",
        ),
        (
            (
                "work-log",
                "list",
                "--context-ref",
                "inbox_wl_" + "a" * 24,
            ),
            "work_log.context_ref_invalid",
        ),
        (
            ("work-log", "show", "raw-memory-id"),
            "work_log.id_invalid",
        ),
        (
            ("work-log", "list", "--limit", "201"),
            "work_log.limit_invalid",
        ),
    ],
)
def test_work_log_invalid_input_has_stable_failure_and_no_traceback(
    tmp_path, args, expected_code
):
    result = _run(tmp_path, *args)
    assert result.returncode == 2
    assert expected_code in result.stderr
    assert "traceback" not in (result.stdout + result.stderr).casefold()


def test_cli_runtime_not_configured_uses_stable_failure(
    tmp_path, monkeypatch
):
    from cli import runtime

    class System:
        work_log_service = None

        async def start(self):
            pass

        async def shutdown(self):
            pass

    monkeypatch.setattr(runtime, "load_system_settings", lambda: object())
    monkeypatch.setattr(
        runtime,
        "create_system",
        lambda _settings: asyncio.sleep(0, result=System()),
    )
    with pytest.raises(FailureException) as failure:
        asyncio.run(
            runtime.execute_work_log_operation(
                "list",
                workspace_key=WorkspaceKey(trace_id="cli-not-configured"),
                limit=50,
                offset=0,
            )
        )
    assert failure.value.failure.code == "work_log.not_configured"
    assert failure.value.failure.trace_id == "cli-not-configured"
