"""Resolve the AI-Lab product version from its canonical packaging source."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import tomllib

_DISTRIBUTION_NAME = "ai-lab"


class VersionResolutionError(RuntimeError):
    """Raised when neither package metadata nor source metadata is usable."""


def _source_pyproject_path() -> Path:
    return Path(__file__).resolve().parents[1] / "pyproject.toml"


def _read_source_version(pyproject_path: Path | None = None) -> str:
    path = pyproject_path or _source_pyproject_path()
    try:
        project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise VersionResolutionError(
            "AI-Lab source version could not be read from pyproject.toml"
        ) from exc

    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise VersionResolutionError(
            "AI-Lab source version is missing from pyproject.toml"
        )
    return version.strip()


def resolve_version() -> str:
    """Prefer installed metadata and fall back to the source checkout."""

    try:
        return metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return _read_source_version()
