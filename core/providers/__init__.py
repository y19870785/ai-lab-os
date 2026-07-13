"""Provider Layer.

AI-Lab's unified provider abstraction layer.
All upper layers (Knowledge, Agent, Application) access external
capabilities through these protocols — never through direct SDK calls.

Sub-modules:
- llm/       : LLM Provider (generate, stream, count_tokens)
- embedding/ : Embedding Provider (embed, embed_query)
- vector/    : Vector DB Provider (insert, search, delete)
- storage/   : Storage Provider (save, load, delete)
"""

from core.providers.base import BaseProvider
from core.providers.models import (
    ProviderType, ProviderStatus, ProviderCapability, ProviderInfo, ProviderConfig,
)
from core.providers.registry import ProviderRegistry
from core.providers.factory import ProviderFactory
from core.providers.exceptions import (
    ProviderError, ProviderNotFoundError, ProviderNotReadyError,
    ProviderOperationError, ProviderConfigurationError, ProviderTimeoutError,
)
from core.providers.retry import RetryPolicy, RetryConfig, RetryResult
from core.providers.cache import ProviderCache, CacheConfig, CacheEntry
from core.providers.metrics import (
    ProviderMetrics, OperationMetrics, MetricsCollector,
)
from core.providers.config import default_configs

__all__ = [
    # Base
    "BaseProvider",
    # Models
    "ProviderType", "ProviderStatus", "ProviderCapability",
    "ProviderInfo", "ProviderConfig",
    # Registry + Factory
    "ProviderRegistry", "ProviderFactory",
    # Exceptions
    "ProviderError", "ProviderNotFoundError", "ProviderNotReadyError",
    "ProviderOperationError", "ProviderConfigurationError", "ProviderTimeoutError",
    # Infra
    "RetryPolicy", "RetryConfig", "RetryResult",
    "ProviderCache", "CacheConfig", "CacheEntry",
    "ProviderMetrics", "OperationMetrics", "MetricsCollector",
    # Config
    "default_configs",
]
