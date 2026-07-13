"""Application Config。"""
from dataclasses import dataclass, field

@dataclass
class ApplicationConfig:
    max_concurrent: int = 10
    default_timeout: int = 300
    enable_workspace_isolation: bool = True
    provider_mode: str = "auto"  # auto | mock | real
    default_model: str = "gpt-4o-mini"
    log_level: str = "INFO"
