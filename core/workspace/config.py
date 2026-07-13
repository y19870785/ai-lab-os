"""Workspace Config —— 默认配置。"""
from dataclasses import dataclass

@dataclass
class WorkspaceConfig:
    default_namespace: str = "default"
    max_workspaces_per_tenant: int = 100
    enable_namespace_isolation: bool = True
    auto_create_default_workspace: bool = True
