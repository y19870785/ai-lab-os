"""Provider Retry Policy.

Unified retry mechanism for all provider operations.
Supports exponential backoff, max retries, and retryable error detection.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.providers.exceptions import ProviderError


@dataclass
class RetryConfig:
    """Retry policy configuration."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        ProviderError,
    )


@dataclass
class RetryResult:
    """Result of a retried operation."""
    success: bool
    result: Any = None
    attempts: int = 0
    total_delay_ms: float = 0.0
    last_error: Exception | None = None


class RetryPolicy:
    """Retry policy executor.

    Usage:
        policy = RetryPolicy(RetryConfig(max_retries=3))
        result = await policy.execute(my_async_fn, arg1, arg2)
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        self._config = config or RetryConfig()

    async def execute(self, fn: Callable, *args: Any, **kwargs: Any) -> RetryResult:
        """Execute fn with retry on failure.

        Args:
            fn: Async callable to execute.
            *args, **kwargs: Passed to fn.

        Returns:
            RetryResult with success, result, attempts, and timing.
        """
        last_error: Exception | None = None
        delay = self._config.base_delay_seconds
        start = time.time()

        for attempt in range(self._config.max_retries + 1):
            try:
                result = await fn(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                return RetryResult(
                    success=True, result=result, attempts=attempt + 1,
                    total_delay_ms=elapsed,
                )
            except Exception as e:
                last_error = e

                # Check if retryable
                if not self._is_retryable(e):
                    break

                if attempt < self._config.max_retries:
                    wait = min(delay, self._config.max_delay_seconds)
                    if self._config.jitter:
                        import random
                        wait *= 0.5 + random.random()
                    await asyncio.sleep(wait)
                    delay *= self._config.backoff_multiplier

        elapsed = (time.time() - start) * 1000
        return RetryResult(
            success=False, attempts=attempt + 1,
            total_delay_ms=elapsed, last_error=last_error,
        )

    def _is_retryable(self, exc: Exception) -> bool:
        """Check if an exception should trigger a retry."""
        return isinstance(exc, self._config.retryable_exceptions)

    @property
    def config(self) -> RetryConfig:
        return self._config
