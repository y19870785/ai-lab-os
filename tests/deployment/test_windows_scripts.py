"""Failure-injection tests for the Windows setup and start contracts."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(
    os.name != "nt" or shutil.which("cmd.exe") is None,
    reason="Windows batch-script tests require cmd.exe",
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "scripts"

FAKE_PYTHON = r"""@echo off
if not defined FAKE_PIP_EXIT set "FAKE_PIP_EXIT=0"
if not defined FAKE_PYTEST_EXIT set "FAKE_PYTEST_EXIT=0"
if not defined FAKE_CLI_EXIT set "FAKE_CLI_EXIT=0"
if not defined FAKE_UVICORN_EXIT set "FAKE_UVICORN_EXIT=0"
if "%1"=="--version" (
  echo Python 3.12.0
  exit /b 0
)
if "%1"=="-c" goto python_code
if "%1"=="-m" goto python_module
exit /b 0

:python_code
if not defined FAKE_C_COUNT set "FAKE_C_COUNT=0"
set /a FAKE_C_COUNT+=1
if "%FAKE_C_COUNT%"=="1" exit /b 0
if "%FAKE_C_COUNT%"=="2" goto product_version
echo mock
exit /b 0

:product_version
if defined FAKE_VERSION_EXIT exit /b %FAKE_VERSION_EXIT%
echo 0.33.0
exit /b 0

:python_module
if "%2"=="pip" exit /b %FAKE_PIP_EXIT%
if "%2"=="pytest" exit /b %FAKE_PYTEST_EXIT%
if "%2"=="cli" exit /b %FAKE_CLI_EXIT%
if "%2"=="uvicorn" exit /b %FAKE_UVICORN_EXIT%
exit /b 0
"""


def _fake_python(tmp_path: Path) -> Path:
    path = tmp_path / "python.cmd"
    path.write_text(FAKE_PYTHON, encoding="utf-8")
    return path


def _run(script: str, tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "AI_LAB_PYTHON": str(_fake_python(tmp_path)),
        "AI_LAB_SETUP_ROOT": str(tmp_path),
        "AI_LAB_RUNTIME_ROOT": str(tmp_path),
        "AI_LAB_SETUP_NONINTERACTIVE": "1",
        "AI_LAB_NONINTERACTIVE": "1",
    })
    env.update(overrides)
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(SCRIPTS / script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )


def test_setup_propagates_dependency_install_failure(tmp_path):
    result = _run("setup.bat", tmp_path, FAKE_PIP_EXIT="17")
    assert result.returncode == 1
    assert "Dependency installation failed" in result.stdout
    assert "Setup complete" not in result.stdout


def test_setup_propagates_test_failure(tmp_path):
    result = _run("setup.bat", tmp_path, FAKE_PYTEST_EXIT="19")
    assert result.returncode == 1
    assert "Test health check failed" in result.stdout
    assert "Setup complete" not in result.stdout


def test_setup_reports_success_only_after_all_steps(tmp_path):
    result = _run("setup.bat", tmp_path)
    assert result.returncode == 0
    assert "Setup complete" in result.stdout


def test_start_propagates_version_resolution_failure(tmp_path):
    result = _run("start.bat", tmp_path, FAKE_VERSION_EXIT="23")
    assert result.returncode == 1
    assert "version resolution failed" in result.stdout


def test_start_propagates_cli_exit_code(tmp_path):
    result = _run("start.bat", tmp_path, FAKE_CLI_EXIT="7")
    assert result.returncode == 7
    assert "exited with code 7" in result.stdout
    assert "closed" not in result.stdout


def test_start_api_propagates_uvicorn_exit_code(tmp_path):
    result = _run("start_api.bat", tmp_path, FAKE_UVICORN_EXIT="9")
    assert result.returncode == 9
    assert "exited with code 9" in result.stdout
    assert "closed" not in result.stdout
