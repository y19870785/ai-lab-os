"""Application Manifest Loader —— 从 YAML 加载应用清单。"""
from __future__ import annotations
from pathlib import Path
import yaml
from applications.models import ApplicationManifest

def load_manifest(path: str | Path) -> ApplicationManifest:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ApplicationManifest(**data)

def validate_manifest(manifest: ApplicationManifest) -> list[str]:
    errors = []
    if not manifest.name: errors.append("name is required")
    if not manifest.version: errors.append("version is required")
    if not manifest.entrypoint: errors.append("entrypoint is required")
    return errors
