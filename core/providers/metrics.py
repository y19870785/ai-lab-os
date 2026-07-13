"""Provider Metrics.

Tracks per-provider operational metrics: requests, success/failure rates,
latency, retry counts, cache hit rates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperationMetrics:
    """Metrics for a single operation type (e.g. "llm.generate")."""
    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    retry_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def success_rate(self) -> float:
        if self.count == 0:
            return 1.0
        return self.success_count / self.count

    @property
    def avg_latency_ms(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_latency_ms / self.count

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.count += 1
        self.success_count += 1
        self.total_latency_ms += latency_ms

    def record_failure(self, latency_ms: float = 0.0) -> None:
        self.count += 1
        self.failure_count += 1
        self.total_latency_ms += latency_ms

    def record_retry(self) -> None:
        self.retry_count += 1

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "retry_count": self.retry_count,
            "cache_hit_rate": (
                self.cache_hits / (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses) > 0 else 0.0
            ),
        }


@dataclass
class ProviderMetrics:
    """Per-provider metrics aggregator."""
    provider_id: str
    provider_type: str
    operations: dict[str, OperationMetrics] = field(default_factory=dict)

    def get_or_create_op(self, op_name: str) -> OperationMetrics:
        """Get or create an operation metric tracker."""
        if op_name not in self.operations:
            self.operations[op_name] = OperationMetrics()
        return self.operations[op_name]

    def record(self, operation: str, success: bool, latency_ms: float = 0.0) -> None:
        """Record an operation result."""
        op = self.get_or_create_op(operation)
        if success:
            op.record_success(latency_ms)
        else:
            op.record_failure(latency_ms)

    def snapshot(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_type": self.provider_type,
            "operations": {
                name: op.snapshot() for name, op in self.operations.items()
            },
        }


class MetricsCollector:
    """Aggregated metrics across all providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderMetrics] = {}

    def get_or_create(self, provider_id: str, provider_type: str) -> ProviderMetrics:
        if provider_id not in self._providers:
            self._providers[provider_id] = ProviderMetrics(
                provider_id=provider_id, provider_type=provider_type,
            )
        return self._providers[provider_id]

    def record(self, provider_id: str, provider_type: str,
               operation: str, success: bool, latency_ms: float = 0.0) -> None:
        m = self.get_or_create(provider_id, provider_type)
        m.record(operation, success, latency_ms)

    def snapshot(self) -> dict[str, Any]:
        return {
            pid: m.snapshot() for pid, m in self._providers.items()
        }

    def clear(self) -> None:
        self._providers.clear()

    @property
    def provider_count(self) -> int:
        return len(self._providers)
