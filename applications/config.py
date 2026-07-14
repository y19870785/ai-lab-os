"""Application Config。"""
from dataclasses import dataclass, field

@dataclass
class ApplicationConfig:
    max_concurrent: int = 10
    default_timeout: int = 300
    enable_workspace_isolation: bool = True
    provider_mode: str = "invalid"  # injected by the Composition Root
    default_model: str = ""  # empty delegates model selection to the injected provider
    log_level: str = "INFO"
