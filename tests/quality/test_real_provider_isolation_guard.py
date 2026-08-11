"""QUALITY-004 真实 Provider 凭据隔离保护回归。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "conftest.py"
CLI_OPT_IN = "--run-real-provider"
ENV_OPT_IN = "AI_LAB_ALLOW_REAL_PROVIDER_TESTS"


def _build_canary_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """构造只会在危险目录被导入/执行时留下标记的隔离项目。"""
    shutil.copy2(GUARD, tmp_path / "conftest.py")
    real_root = tmp_path / "tests" / "real"
    real_root.mkdir(parents=True)
    imported = tmp_path / "real-imported"
    executed = tmp_path / "real-executed"
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=fake-provider-credential-for-isolation-test\n",
        encoding="utf-8",
    )
    (real_root / "conftest.py").write_text(
        "from dotenv import load_dotenv\nload_dotenv()\n",
        encoding="utf-8",
    )
    (real_root / "test_canary.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(imported)!r}).write_text('imported', encoding='utf-8')\n\n"
        "def test_real_provider_canary():\n"
        f"    Path({str(executed)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return tmp_path, imported, executed


def _run_pytest(
    project: Path,
    *arguments: str,
    environment: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key, value in (environment or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=project,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


@pytest.mark.parametrize(
    ("arguments", "environment"),
    [
        ((), {ENV_OPT_IN: None}),
        ((), {"OPENAI_API_KEY": "fake-nonempty-provider-key", ENV_OPT_IN: None}),
        ((CLI_OPT_IN,), {ENV_OPT_IN: None}),
        ((), {ENV_OPT_IN: "1"}),
        (
            (),
            {
                "OPENAI_API_KEY": "",
                "AI_LAB_LLM_API_KEY": "",
                ENV_OPT_IN: None,
            },
        ),
        (
            (),
            {
                "OPENAI_API_KEY": "DISABLED",
                "AI_LAB_LLM_API_KEY": "DISABLED",
                ENV_OPT_IN: None,
            },
        ),
    ],
    ids=[
        "plain-pytest-with-dotenv",
        "credential-without-opt-in",
        "cli-only",
        "environment-only",
        "empty-environment-with-dotenv",
        "disabled-sentinel",
    ],
)
def test_real_provider_directory_is_not_imported_without_two_factors(
    tmp_path: Path,
    arguments: tuple[str, ...],
    environment: dict[str, str | None],
) -> None:
    project, imported, executed = _build_canary_project(tmp_path)

    result = _run_pytest(project, *arguments, "--collect-only", environment=environment)

    assert result.returncode == 5
    assert not imported.exists()
    assert not executed.exists()


def test_default_collection_explains_the_fail_closed_guard(tmp_path: Path) -> None:
    project, imported, executed = _build_canary_project(tmp_path)

    result = _run_pytest(project, "--collect-only", environment={ENV_OPT_IN: None})

    assert result.returncode == 5
    assert "Real-provider tests disabled" in result.stdout
    assert not imported.exists()
    assert not executed.exists()


def test_double_opt_in_allows_collection_without_execution(tmp_path: Path) -> None:
    project, imported, executed = _build_canary_project(tmp_path)

    result = _run_pytest(
        project,
        CLI_OPT_IN,
        "--collect-only",
        environment={ENV_OPT_IN: "1"},
    )

    assert result.returncode == 0
    assert imported.exists()
    assert not executed.exists()
    assert "1 test collected" in result.stdout
