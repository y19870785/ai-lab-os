"""SP-020 direct Daily Review CLI contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(tmp_path, *args: str):
    env = os.environ.copy()
    env.update({
        "AI_LAB_DATA_DIR": str(tmp_path),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_ENABLE_REMINDERS": "false",
        "AI_LAB_ENABLE_SCHEDULER": "false",
        "AI_LAB_API_AUTH_ENABLED": "false",
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_TENANT_ID": "tenant-cli",
        "AI_LAB_WORKSPACE_ID": "workspace-cli",
        "AI_LAB_NAMESPACE": "daily",
        "AI_LAB_SESSION_ID": "session-cli",
        "AI_LAB_AGENT_ID": "agent-cli",
        "PYTHONIOENCODING": "utf-8",
    })
    for name in (
        "AI_LAB_LLM_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ALL_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "http_proxy",
        "https_proxy",
    ):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, "-m", "cli", "daily-review", *args],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


def test_daily_review_cli_today_json_preserves_structured_facts(tmp_path):
    result = _run(tmp_path, "--date", "today", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["workspace"] == {
        "tenant_id": "tenant-cli",
        "workspace_id": "workspace-cli",
        "namespace": "daily",
    }
    assert payload["timezone"] == "Asia/Shanghai"
    assert payload["page"]["limit"] == 50
    assert payload["page"]["offset"] == 0
    assert set(payload["source_status"]) == {
        "work_log",
        "user_task",
        "waiting_for",
        "reminder",
        "inbox",
    }


def test_daily_review_cli_yesterday_human_and_invalid_date(tmp_path):
    human = _run(tmp_path, "--date", "yesterday")
    assert human.returncode == 0, human.stderr
    assert "每日复盘" in human.stdout
    assert "limit=50" in human.stdout
    invalid = _run(tmp_path, "--date", "tomorrow")
    assert invalid.returncode != 0
    assert "invalid choice" in invalid.stderr
