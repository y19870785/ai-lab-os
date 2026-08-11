"""QUALITY-004 真实 Provider 凭据隔离保护回归。"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "conftest.py"
REAL_TEST_ROOT = ROOT / "tests" / "real"
CLI_OPT_IN = "--run-real-provider"
ENV_OPT_IN = "AI_LAB_ALLOW_REAL_PROVIDER_TESTS"
FAKE_CREDENTIAL = "fake-provider-credential-for-isolation-test"
PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "AI_LAB_LLM_API_KEY",
    "AI_LAB_LLM_BASE_URL",
    "AI_LAB_LLM_MODEL",
    ENV_OPT_IN,
)


def _build_canary_project(tmp_path: Path) -> dict[str, Path]:
    """构造可观测 import、dotenv 与 test execution 的隔离项目。"""
    shutil.copy2(GUARD, tmp_path / "conftest.py")
    real_root = tmp_path / "tests" / "real"
    real_root.mkdir(parents=True)
    normal_root = tmp_path / "tests"
    markers = {
        name: tmp_path / name
        for name in (
            "real-conftest-imported",
            "dotenv-loaded",
            "real-module-imported",
            "real-test-executed",
            "normal-test-executed",
            "normal-observed-dotenv-credential",
        )
    }
    (tmp_path / ".env").write_text(
        f"OPENAI_API_KEY={FAKE_CREDENTIAL}\n",
        encoding="utf-8",
    )
    (real_root / "conftest.py").write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "import pytest\n"
        "from dotenv import load_dotenv\n\n"
        f"Path({str(markers['real-conftest-imported'])!r}).write_text("
        "'imported', encoding='utf-8')\n\n"
        "@pytest.fixture(scope='session')\n"
        "def real_provider_environment(pytestconfig):\n"
        f"    if not pytestconfig.getoption({CLI_OPT_IN!r}):\n"
        "        pytest.skip('CLI authorization absent')\n"
        f"    if os.getenv({ENV_OPT_IN!r}) != '1':\n"
        "        pytest.skip('environment authorization absent')\n"
        "    load_dotenv()\n"
        f"    Path({str(markers['dotenv-loaded'])!r}).write_text("
        "os.getenv('OPENAI_API_KEY', ''), encoding='utf-8')\n",
        encoding="utf-8",
    )
    (real_root / "test_canary.py").write_text(
        "from pathlib import Path\n\n"
        "import pytest\n\n"
        "pytestmark = pytest.mark.real\n"
        f"Path({str(markers['real-module-imported'])!r}).write_text("
        "'imported', encoding='utf-8')\n\n"
        "def test_real_provider_canary(real_provider_environment):\n"
        f"    Path({str(markers['real-test-executed'])!r}).write_text("
        "'executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (normal_root / "test_normal_canary.py").write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "def test_normal_canary():\n"
        f"    observed = os.getenv('OPENAI_API_KEY') == {FAKE_CREDENTIAL!r}\n"
        "    if observed:\n"
        f"        Path({str(markers['normal-observed-dotenv-credential'])!r})"
        ".write_text('observed', encoding='utf-8')\n"
        f"    Path({str(markers['normal-test-executed'])!r}).write_text("
        "'executed', encoding='utf-8')\n"
        "    assert not observed\n",
        encoding="utf-8",
    )
    markers["project"] = tmp_path
    markers["real_file"] = real_root / "test_canary.py"
    markers["normal_file"] = normal_root / "test_normal_canary.py"
    return markers


def _run_pytest(
    project: Path,
    *arguments: str,
    environment: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in PROVIDER_ENV_KEYS:
        env.pop(key, None)
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


def _assert_no_real_side_effect(markers: dict[str, Path]) -> None:
    assert not markers["dotenv-loaded"].exists()
    assert not markers["real-test-executed"].exists()
    assert not markers["normal-observed-dotenv-credential"].exists()


def test_plain_pytest_with_dotenv_executes_only_normal_test(tmp_path: Path) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(markers["project"], "-q")

    assert result.returncode == 0
    assert markers["normal-test-executed"].exists()
    assert not markers["real-conftest-imported"].exists()
    assert not markers["real-module-imported"].exists()
    _assert_no_real_side_effect(markers)


@pytest.mark.parametrize(
    ("arguments", "environment"),
    [
        ((), {"OPENAI_API_KEY": "fake-nonempty-provider-key"}),
        ((CLI_OPT_IN,), {}),
        ((), {ENV_OPT_IN: "1"}),
        ((), {"OPENAI_API_KEY": "", "AI_LAB_LLM_API_KEY": ""}),
        (
            (),
            {
                "OPENAI_API_KEY": "DISABLED",
                "AI_LAB_LLM_API_KEY": "DISABLED",
            },
        ),
    ],
    ids=[
        "credential-without-opt-in",
        "cli-only",
        "environment-only",
        "empty-environment-with-dotenv",
        "disabled-sentinel",
    ],
)
def test_default_collection_excludes_real_directory_without_two_factors(
    tmp_path: Path,
    arguments: tuple[str, ...],
    environment: dict[str, str | None],
) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(
        markers["project"],
        *arguments,
        "--collect-only",
        environment=environment,
    )

    assert result.returncode == 0
    assert not markers["real-conftest-imported"].exists()
    assert not markers["real-module-imported"].exists()
    _assert_no_real_side_effect(markers)


def test_default_collection_explains_the_fail_closed_guard(tmp_path: Path) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(markers["project"], "--collect-only")

    assert result.returncode == 0
    assert "Real-provider tests disabled" in result.stdout
    _assert_no_real_side_effect(markers)


def test_double_opt_in_allows_collection_without_execution(tmp_path: Path) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(
        markers["project"],
        CLI_OPT_IN,
        "--collect-only",
        environment={ENV_OPT_IN: "1"},
    )

    assert result.returncode == 0
    assert markers["real-conftest-imported"].exists()
    assert markers["real-module-imported"].exists()
    assert "2 tests collected" in result.stdout
    _assert_no_real_side_effect(markers)


@pytest.mark.parametrize(
    "selection",
    [
        ("tests/real",),
        ("tests/real/test_canary.py",),
        ("tests/real/test_canary.py::test_real_provider_canary",),
    ],
    ids=["explicit-real-directory", "explicit-real-file", "explicit-real-node"],
)
def test_explicit_real_selection_is_import_safe_without_authorization(
    tmp_path: Path,
    selection: tuple[str, ...],
) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(markers["project"], *selection, "-q")

    assert result.returncode in {0, 5}
    _assert_no_real_side_effect(markers)


def test_mixed_real_and_normal_selection_does_not_leak_dotenv(
    tmp_path: Path,
) -> None:
    markers = _build_canary_project(tmp_path)

    result = _run_pytest(
        markers["project"],
        "tests/real/test_canary.py",
        "tests/test_normal_canary.py",
        "-q",
    )

    assert result.returncode == 0
    assert markers["normal-test-executed"].exists()
    _assert_no_real_side_effect(markers)


def _call_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def test_real_test_modules_have_no_dangerous_module_scope_calls() -> None:
    forbidden = {
        "load_dotenv",
        "skipif",
        "OpenAI",
        "AsyncOpenAI",
        "create_system",
        "request",
        "get",
        "post",
    }
    violations: list[str] = []

    for path in sorted(REAL_TEST_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for node in ast.walk(statement):
                if isinstance(node, ast.Call) and _call_name(node) in forbidden:
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []


def test_real_provider_environment_checks_authorization_before_dotenv() -> None:
    source = (REAL_TEST_ROOT / "conftest.py").read_text(encoding="utf-8-sig")

    cli_check = source.index('pytestconfig.getoption("--run-real-provider")')
    environment_check = source.index('os.getenv("AI_LAB_ALLOW_REAL_PROVIDER_TESTS")')
    dotenv_call = source.index("    load_dotenv()")
    credential_check = source.index('os.getenv("AI_LAB_LLM_API_KEY")')

    assert cli_check < environment_check < dotenv_call < credential_check


def test_real_files_can_be_imported_without_loading_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        f"OPENAI_API_KEY={FAKE_CREDENTIAL}\n",
        encoding="utf-8",
    )
    script = (
        "import os,runpy;"
        "assert 'OPENAI_API_KEY' not in os.environ;"
        f"runpy.run_path({str(REAL_TEST_ROOT / 'conftest.py')!r});"
        f"runpy.run_path({str(REAL_TEST_ROOT / 'test_ceo_assistant_deepseek.py')!r});"
        "assert 'OPENAI_API_KEY' not in os.environ"
    )
    env = os.environ.copy()
    for key in PROVIDER_ENV_KEYS:
        env.pop(key, None)

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
