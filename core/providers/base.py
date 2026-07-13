"""BaseProvider — unified lifecycle for all providers.

Every provider MUST extend BaseProvider. It defines the contract for:
- initialize() / shutdown() — lifecycle
- health_check() / is_available() — readiness
- metadata() / capabilities() — introspection
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.providers.models import ProviderCapability, ProviderInfo, ProviderStatus
from core.providers.exceptions import ProviderNotReadyError


class BaseProvider(ABC):
    """Abstract base for all providers.

    Subclasses implement the abstract methods. The base class manages
    status transitions and provides common lifecycle guards.

    Usage:
        class MyLLM(BaseProvider):
            async def _do_initialize(self) -> None: ...
            async def _do_shutdown(self) -> None: ...
            async def _do_health_check(self) -> bool: ...
    """

    def __init__(self, info: ProviderInfo) -> None:
        self._info = info
        self._info.status = ProviderStatus.UNINITIALIZED

    # ── Public lifecycle ──

    async def initialize(self) -> None:
        """Initialize the provider. Idempotent — skips if already READY."""
        if self._info.status == ProviderStatus.READY:
            return
        if self._info.status == ProviderStatus.INITIALIZING:
            return
        self._info.status = ProviderStatus.INITIALIZING
        try:
            await self._do_initialize()
            self._info.status = ProviderStatus.READY
        except Exception:
            self._info.status = ProviderStatus.UNAVAILABLE
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown the provider. Idempotent."""
        if self._info.status == ProviderStatus.SHUTDOWN:
            return
        try:
            await self._do_shutdown()
        finally:
            self._info.status = ProviderStatus.SHUTDOWN

    async def health_check(self) -> bool:
        """Check if provider is operational. Returns True/False."""
        if self._info.status != ProviderStatus.READY:
            return False
        try:
            ok = await self._do_health_check()
            if not ok:
                self._info.status = ProviderStatus.DEGRADED
            return ok
        except Exception:
            self._info.status = ProviderStatus.DEGRADED
            return False

    def is_available(self) -> bool:
        """Is provider ready for use?"""
        return self._info.status in (ProviderStatus.READY, ProviderStatus.DEGRADED)

    def _require_ready(self) -> None:
        """Guard: raise if not ready."""
        if not self.is_available():
            raise ProviderNotReadyError(self._info.provider_id, self._info.status.value)

    # ── Introspection ──

    def metadata(self) -> ProviderInfo:
        """Return current provider metadata (includes live status)."""
        return self._info

    def capabilities(self) -> list[ProviderCapability]:
        """Return this provider's declared capabilities."""
        return list(self._info.capabilities)

    def has_capability(self, name: str) -> bool:
        """Check if provider declares a specific capability."""
        return any(c.name == name for c in self._info.capabilities)

    # ── Subclass hooks ──

    @abstractmethod
    async def _do_initialize(self) -> None:
        """Provider-specific initialization logic."""
        ...

    @abstractmethod
    async def _do_shutdown(self) -> None:
        """Provider-specific cleanup logic."""
        ...

    @abstractmethod
    async def _do_health_check(self) -> bool:
        """Provider-specific health check. Return True if healthy."""
        ...
