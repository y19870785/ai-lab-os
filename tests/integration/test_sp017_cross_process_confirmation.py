import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _env(tmp_path):
    env = os.environ.copy()
    env.update({
        "AI_LAB_DATA_DIR": str(tmp_path),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_ENABLE_REMINDERS": "false",
        "AI_LAB_ENABLE_SCHEDULER": "false",
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_API_AUTH_ENABLED": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    for key in ("AI_LAB_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        env.pop(key, None)
    return env


def test_two_processes_confirm_one_inbox_into_one_waiting_for(tmp_path):
    env = _env(tmp_path)
    added = subprocess.run(
        [sys.executable, "-m", "cli", "inbox", "add", "等待张经理回复", "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert added.returncode == 0, added.stderr
    inbox_id = json.loads(added.stdout)["id"]
    command = [
        sys.executable,
        "-m",
        "cli",
        "inbox",
        "resolve-waiting-for",
        inbox_id,
        "--subject",
        "蜂蜡检测方案",
        "--waiting-on",
        "张经理",
        "--next-review-at",
        "2026-07-25T09:00:00+08:00",
        "--timezone",
        "Asia/Shanghai",
        "--json",
    ]

    first = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    second = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    first_out, first_err = first.communicate(timeout=60)
    second_out, second_err = second.communicate(timeout=60)

    assert first.returncode == 0, first_err
    assert second.returncode == 0, second_err
    first_target = json.loads(first_out)["resolved_target_id"]
    second_target = json.loads(second_out)["resolved_target_id"]
    assert first_target == second_target

    listed = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "waiting-for",
            "list",
            "--view",
            "all",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert listed.returncode == 0, listed.stderr
    items = json.loads(listed.stdout)["items"]
    assert [item["id"] for item in items] == [first_target]
