"""SP-020 Local Daily Profile validation and secret-safe diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.system.settings import load_system_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _profile_env(monkeypatch, tmp_path: Path) -> None:
    values = {
        "AI_LAB_PROFILE": "local-daily",
        "AI_LAB_DATA_DIR": str(tmp_path / "data"),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "data" / "sqlite"),
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_ENABLE_USER_TASKS": "true",
        "AI_LAB_ENABLE_DAILY_REVIEW": "true",
        "AI_LAB_ENABLE_REMINDERS": "true",
        "AI_LAB_ENABLE_SCHEDULER": "true",
        "AI_LAB_ENABLE_KNOWLEDGE": "false",
        "AI_LAB_ENABLE_COORDINATION": "false",
        "AI_LAB_ENABLE_API": "true",
        "AI_LAB_API_AUTH_ENABLED": "true",
        "AI_LAB_API_TOKEN": "top-secret-token",
        "AI_LAB_API_BIND": "127.0.0.1",
        "AI_LAB_TENANT_ID": "tenant-local",
        "AI_LAB_WORKSPACE_ID": "workspace-daily",
        "AI_LAB_NAMESPACE": "operations",
        "AI_LAB_SESSION_ID": "windows-session",
        "AI_LAB_AGENT_ID": "owner",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_local_daily_profile_is_absolute_complete_and_secret_safe(
    monkeypatch, tmp_path
):
    _profile_env(monkeypatch, tmp_path)
    settings = load_system_settings(load_dotenv=False)
    summary = settings.safe_summary(project_root=tmp_path)

    assert settings.data_dir.is_absolute()
    assert settings.sqlite_dir.is_relative_to(settings.data_dir)
    assert summary["api_token"] == "configured"
    assert summary["provider_secret"] == "not configured"
    assert "top-secret-token" not in str(summary)
    assert summary["workspace"] == {
        "tenant_id": "tenant-local",
        "workspace_id": "workspace-daily",
        "namespace": "operations",
        "session_id": "windows-session",
        "agent_id": "owner",
    }


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("AI_LAB_DATA_DIR", "relative-data", "absolute"),
        ("AI_LAB_SQLITE_DIR", "relative-sqlite", "absolute"),
        ("AI_LAB_TIMEZONE", "Mars/Olympus", "IANA"),
        ("AI_LAB_PROVIDER_MODE", "invalid", "mock, test, or real"),
        ("AI_LAB_API_TOKEN", "", "missing explicit settings"),
        ("AI_LAB_API_BIND", "0.0.0.0", "127.0.0.1"),
        ("AI_LAB_ENABLE_SCHEDULER", "false", "feature flags"),
    ],
)
def test_local_daily_profile_fails_closed(
    monkeypatch, tmp_path, name, value, message
):
    _profile_env(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        load_system_settings(load_dotenv=False)


@pytest.mark.parametrize(
    "profile",
    ["local_daily", "localdaily", "local-day", "production", "invalid"],
)
def test_unknown_nonempty_profile_fails_closed(monkeypatch, profile):
    monkeypatch.setenv("AI_LAB_PROFILE", profile)
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
    with pytest.raises(ValueError, match="Unsupported AI_LAB_PROFILE"):
        load_system_settings(load_dotenv=False)


def test_empty_profile_keeps_legacy_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_LAB_PROFILE", "")
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
    monkeypatch.delenv("AI_LAB_DATA_DIR", raising=False)
    settings = load_system_settings(
        project_root=tmp_path,
        load_dotenv=False,
    )
    assert settings.profile_name == ""
    assert settings.data_dir == (tmp_path / "data").resolve()


def test_local_daily_startup_script_supports_windows_powershell() -> None:
    script = (PROJECT_ROOT / "scripts" / "start-local-daily.ps1").read_text(
        encoding="utf-8"
    )

    assert "$PSScriptRoot" in script
    assert "IsPathRooted($env:AI_LAB_PYTHON)" in script
    assert "GetFullPath($env:AI_LAB_PYTHON, $ProjectRoot)" not in script
    assert "--require-local-daily" in script
    assert "--host 127.0.0.1" in script
