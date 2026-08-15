"""Static release-contract checks; wheel construction remains a release gate."""

import ast
import json
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _project_config() -> dict:
    return tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


def _names(requirements: list[str]) -> set[str]:
    return {item.split(">=", 1)[0].lower() for item in requirements}


def test_dependency_extras_match_runtime_boundaries():
    config = _project_config()["project"]
    extras = config["optional-dependencies"]

    assert _names(config["dependencies"]) == {
        "cryptography",
        "pydantic",
        "pyyaml",
        "python-dotenv",
        "rfc8785",
        "tzdata",
    }
    assert any(
        requirement.startswith("tzdata>=")
        and "platform_system == 'Windows'" in requirement
        for requirement in config["dependencies"]
    )
    assert _names(extras["api"]) == {"fastapi", "uvicorn"}
    assert _names(extras["real"]) == {"openai"}
    assert _names(extras["knowledge"]) == {"chromadb", "sentence-transformers"}
    assert _names(extras["integration"]) == {"mcp"}
    assert {"pytest", "pytest-asyncio", "httpx"} <= _names(extras["test"])
    assert {"build", "twine"} <= _names(extras["build"])
    assert {"ruff", "mypy"} <= _names(extras["dev"])
    assert _names(
        extras["api"]
        + extras["real"]
        + extras["integration"]
        + extras["test"]
        + extras["build"]
        + extras["dev"]
    ) == _names(extras["local"])


def test_setuptools_discovers_product_packages_only():
    package_config = _project_config()["tool"]["setuptools"]["packages"]["find"]
    includes = set(package_config["include"])
    excludes = set(package_config["exclude"])

    canonical_packages = {
        "api*",
        "applications*",
        "cli*",
        "core*",
    }
    deprecated_compatibility_packages = {
        "agents*",
        "knowledge*",
        "workflows*",
    }
    excluded_obsolete_implementation_packages: set[str] = set()
    excluded_non_product_namespaces = {"database*", "prompts*"}
    assert includes == canonical_packages | deprecated_compatibility_packages
    assert not excluded_obsolete_implementation_packages
    assert includes.isdisjoint(excluded_non_product_namespaces)
    assert "tests*" in excludes
    assert "data*" in excludes
    assert "logs*" in excludes
    assert "runtime*" in excludes
    assert (PROJECT_ROOT / "core" / "waiting_for" / "__init__.py").is_file()


@pytest.fixture(scope="module")
def built_distribution_artifacts(tmp_path_factory):
    root = tmp_path_factory.mktemp("packaging-contract")
    source = root / "source"
    shutil.copytree(
        PROJECT_ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv*",
            ".pytest_cache",
            "__pycache__",
            "*.egg-info",
            "build",
            "dist",
        ),
    )
    output = root / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(output),
        ],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    wheel = next(output.glob("*.whl"))
    sdist = next(output.glob("*.tar.gz"))
    return root, wheel, sdist


def test_wheel_and_sdist_retain_deprecated_compatibility_packages(
    built_distribution_artifacts,
):
    _, wheel, sdist = built_distribution_artifacts
    required = ("agents/", "knowledge/", "core/agent/", "workflows/")
    excluded = ("prompts/", "database/")

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = [name.split("/", 1)[1] for name in archive.getnames() if "/" in name]

    for prefix in required:
        assert any(name.startswith(prefix) for name in wheel_names)
        assert any(name.startswith(prefix) for name in sdist_names)
    for prefix in excluded:
        assert not any(name.startswith(prefix) for name in wheel_names)
        assert not any(name.startswith(prefix) for name in sdist_names)


def test_clean_target_install_imports_deprecated_namespaces_with_warnings(
    built_distribution_artifacts,
):
    root, wheel, _ = built_distribution_artifacts
    compatibility_prefixes = ("agents/", "knowledge/", "core/agent/", "workflows/")
    with zipfile.ZipFile(wheel) as archive:
        compatibility_modules = []
        for name in archive.namelist():
            if not name.endswith(".py") or not name.startswith(compatibility_prefixes):
                continue
            module = name.removesuffix(".py").replace("/", ".")
            if module.endswith(".__init__"):
                module = module.removesuffix(".__init__")
            compatibility_modules.append(module)
    compatibility_modules.sort()
    target = root / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    script = """
import importlib
import json
import sys
import warnings

sys.path.insert(0, sys.argv[1])
names = json.loads(sys.argv[2])
canonical_names = ["core.agents", "core.knowledge", "core.workflow"]
imports = []
failures = {}
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", DeprecationWarning)
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures[name] = {"type": type(exc).__name__, "message": str(exc)}
        else:
            imports.append(name)
    for name in canonical_names:
        importlib.import_module(name)
result = {
    "imports": imports,
    "failures": failures,
    "canonical_imports": canonical_names,
    "warnings": [str(item.message) for item in caught],
}
try:
    importlib.import_module("prompts")
except ModuleNotFoundError:
    result["prompts"] = "NOT_PACKAGED_AS_IN_BASE"
else:
    result["prompts"] = "UNEXPECTEDLY_PACKAGED"
print(json.dumps(result))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(target),
            json.dumps(compatibility_modules),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    result = json.loads(completed.stdout)
    expected_base_failures = {"agents.memory", "agents.permission"}
    assert set(result["imports"]) == set(compatibility_modules) - expected_base_failures
    assert set(result["failures"]) == expected_base_failures
    for failure in result["failures"].values():
        assert failure["type"] == "ImportError"
        assert "MemoryType" in failure["message"]
    assert result["canonical_imports"] == [
        "core.agents",
        "core.knowledge",
        "core.workflow",
    ]
    assert result["prompts"] == "NOT_PACKAGED_AS_IN_BASE"
    warning_text = "\n".join(result["warnings"])
    for namespace in ("agents", "knowledge", "core.agent", "workflows"):
        assert namespace in warning_text
    assert "v0.37.0" in warning_text


def test_source_only_prompts_namespace_remains_importable_with_warning(tmp_path):
    script = """
import importlib
import json
import sys
import warnings

sys.path.insert(0, sys.argv[1])
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", DeprecationWarning)
    importlib.import_module("prompts")
print(json.dumps([str(item.message) for item in caught]))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(PROJECT_ROOT)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    warning_text = "\n".join(json.loads(completed.stdout))
    assert "source-only 'prompts' namespace is deprecated" in warning_text
    assert "v0.37.0" in warning_text


def test_removed_package_governance_docs_are_reconciled():
    adr006 = (
        PROJECT_ROOT / "docs/adr/ADR-006-knowledge-storage-strategy.md"
    ).read_text(encoding="utf-8-sig")
    versioning = (
        PROJECT_ROOT / "docs/governance/VERSIONING_POLICY.md"
    ).read_text(encoding="utf-8-sig")
    audit = (PROJECT_ROOT / "docs/project/DEPRECATION_AUDIT.md").read_text(
        encoding="utf-8-sig"
    )

    for marker in (
        "原始 Accepted 决策正文",
        "core/knowledge/protocol.py",
        "core/knowledge/sqlite_store.py",
        "core/knowledge/manager.py",
        "不包含",
        "VectorStore`/`GraphStore",
    ):
        assert marker in adr006
    assert (
        "top-level prompts/ namespace: DEPRECATED_SOURCE_ONLY / NOT_CANONICAL / NOT_PACKAGED"
        in versioning
    )
    assert "v0.35.0 Alpha" in versioning
    assert "FUTURE_PROPOSAL: prompts/config.yaml" in versioning
    for classification in (
        "CURRENT_CONFLICT",
        "HISTORICAL_CONTEXT",
        "FUTURE_PROPOSAL",
        "REMOVAL_RECORD",
    ):
        assert classification in audit
    for marker in (
        "cleanup phase completed",
        "compatibility shims retained",
        "final namespace removal deferred for at least one Minor",
        "cannot prove absence of every unknown external consumer",
        "unknown external consumers cannot be disproven",
    ):
        assert marker in audit


def test_requirements_is_only_a_local_extra_compatibility_entrypoint():
    lines = [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines == ["-e .[local]"]


def test_windows_script_tests_have_a_module_level_platform_gate():
    test_path = PROJECT_ROOT / "tests" / "deployment" / "test_windows_scripts.py"
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "pytestmark"
            for target in node.targets
        )
    ]

    assert len(assignments) == 1
    gate = ast.unparse(assignments[0].value)
    assert "pytest.mark.skipif" in gate
    assert "os.name" in gate
    assert "shutil.which('cmd.exe')" in gate
