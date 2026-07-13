"""Tool System configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
@dataclass
class ToolConfig:
    default_timeout: int = 30
    max_timeout: int = 300
    sandbox_enabled: bool = True
    audit_enabled: bool = True
    metrics_enabled: bool = True
    permission_check_enabled: bool = True
    auto_discover: bool = True