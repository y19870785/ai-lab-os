"""Provider Layer data models.

Defines the metadata types shared by all providers:
- ProviderType: LLM / EMBEDDING / VECTOR / STORAGE
- ProviderStatus: lifecycle states
- ProviderInfo: provider metadata (name, version, caps)
- ProviderCapability: declared capability with version
- ProviderConfig: initialization configuration
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Provider category."""
    LLM = "llm"
    EMBEDDING = "embedding"
    VECTOR = "vector"
    STORAGE = "storage"


class ProviderStatus(str, Enum):
    """Provider lifecycle status."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    SHUTDOWN = "shutdown"


class ProviderCapability(BaseModel):
    """A single capability a provider declares support for."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    """Provider metadata — identity + status + capabilities."""
    provider_id: str
    provider_type: ProviderType
    name: str
    version: str = "0.1.0"
    description: str = ""
    status: ProviderStatus = ProviderStatus.UNINITIALIZED
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class ProviderConfig(BaseModel):
    """Configuration for initializing a provider.

    provider_type + provider_name determine which provider class to instantiate.
    settings holds provider-specific key-value pairs (api keys, endpoints, etc.).
    """
    provider_type: ProviderType
    provider_name: str = "default"
    settings: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
