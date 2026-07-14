"""Product version source and runtime resolution tests."""

from __future__ import annotations

import asyncio
from importlib import metadata
from pathlib import Path

import pytest
import tomllib

import core
from api.app import create_app
from api.routes.health import health_check
from core import _version
from core.config import AppConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_declares_v0330_baseline():
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    assert project["version"] == "0.33.0"


def test_distribution_metadata_matches_runtime_version():
    assert metadata.version("ai-lab") == core.__version__ == "0.33.0"


def test_package_not_found_uses_source_pyproject(monkeypatch):
    def package_not_found(_name: str) -> str:
        raise metadata.PackageNotFoundError("ai-lab")

    monkeypatch.setattr(_version.metadata, "version", package_not_found)
    assert _version.resolve_version() == "0.33.0"


def test_source_fallback_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _version._read_source_version() == "0.33.0"


def test_core_does_not_hardcode_release_version():
    for path in (
        PROJECT_ROOT / "core" / "__init__.py",
        PROJECT_ROOT / "core" / "_version.py",
    ):
        assert "0.33.0" not in path.read_text(encoding="utf-8")


def test_app_config_and_api_use_runtime_version():
    assert AppConfig().version == core.__version__
    assert create_app().version == core.__version__


def test_health_route_uses_runtime_version():
    class HealthySystem:
        async def health(self):
            return {"status": "healthy", "components": {}}

    result = asyncio.run(health_check(HealthySystem()))
    assert result["version"] == core.__version__


@pytest.mark.parametrize(
    "content",
    (None, "not valid toml = [", "[project]\nname = 'ai-lab'\n"),
)
def test_invalid_source_metadata_fails_explicitly(tmp_path, content):
    pyproject = tmp_path / "pyproject.toml"
    if content is not None:
        pyproject.write_text(content, encoding="utf-8")

    with pytest.raises(_version.VersionResolutionError, match="source version"):
        _version._read_source_version(pyproject)
