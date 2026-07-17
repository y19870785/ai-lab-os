import os, json, subprocess, sys
from pathlib import Path
import tempfile


def _run_agenda(args_str, tmp_path, extra_env=None):
    env = os.environ.copy()
    env["AI_LAB_DATA_DIR"] = str(tmp_path)
    env["AI_LAB_SQLITE_DIR"] = str(tmp_path / "sqlite")
    env["AI_LAB_PROVIDER_MODE"] = "mock"
    env["AI_LAB_ENABLE_REMINDERS"] = "true"
    env["AI_LAB_ENABLE_SCHEDULER"] = "true"
    env["AI_LAB_TIMEZONE"] = "Asia/Shanghai"
    env["AI_LAB_API_AUTH_ENABLED"] = "false"
    env["PYTHONIOENCODING"] = "utf-8"
    for k in ("AI_LAB_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
              "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    venv_python = str(Path(__file__).parent.parent.parent / ".venv_312" / "Scripts" / "python.exe")
    cmd = [venv_python, "-m", "cli", "agenda"] + args_str.split()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env,
                          encoding="utf-8", cwd=str(Path(__file__).parent.parent.parent))
    return proc


def test_agenda_cli_today_json_pure_stdout(tmp_path):
    (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)
    proc = _run_agenda("--today --json", tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip()
    data = json.loads(proc.stdout)
    assert data["view"] == "today"
    assert data["timezone"] == "Asia/Shanghai"


def test_agenda_cli_next_3(tmp_path):
    (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)
    proc = _run_agenda("--next 3 --json", tmp_path)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["view"] == "next"


def test_agenda_cli_nonzero_on_error(tmp_path):
    env_bad = {"AI_LAB_ENABLE_REMINDERS": "false"}
    proc = _run_agenda("--today --json", tmp_path, extra_env=env_bad)
    assert proc.returncode != 0
