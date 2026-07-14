"""Static release-contract checks; wheel construction remains a release gate."""

from pathlib import Path

import tomllib


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
        "pydantic",
        "pyyaml",
        "python-dotenv",
    }
    assert _names(extras["api"]) == {"fastapi", "uvicorn"}
    assert _names(extras["real"]) == {"openai"}
    assert _names(extras["knowledge"]) == {"chromadb", "sentence-transformers"}
    assert {"pytest", "pytest-asyncio", "httpx"} <= _names(extras["test"])
    assert {"build", "twine"} <= _names(extras["build"])
    assert {"ruff", "mypy"} <= _names(extras["dev"])
    assert _names(extras["api"] + extras["real"] + extras["test"] +
                  extras["build"] + extras["dev"]) == _names(extras["local"])


def test_setuptools_discovers_product_packages_only():
    package_config = _project_config()["tool"]["setuptools"]["packages"]["find"]
    includes = set(package_config["include"])
    excludes = set(package_config["exclude"])

    assert {"core*", "agents*", "knowledge*", "applications*", "api*", "cli*"} <= includes
    assert "tests*" in excludes
    assert "data*" in excludes
    assert "logs*" in excludes
    assert "runtime*" in excludes


def test_requirements_is_only_a_local_extra_compatibility_entrypoint():
    lines = [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines == ["-e .[local]"]
