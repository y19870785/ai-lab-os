"""ProviderRegistry — central provider registry.

Manages all registered providers. Supports lookup by type, name, and capability.
Providers are registered as factory functions (callable -> BaseProvider),
not as raw instances — the registry manages lazy instantiation.

Usage:
    registry = ProviderRegistry()
    registry.register(ProviderType.LLM, "mock", MockLLMProvider)
    provider = registry.get(ProviderType.LLM, "mock")
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Type

from core.providers.base import BaseProvider
from core.providers.models import ProviderType
from core.providers.exceptions import (
    ProviderError, ProviderNotFoundError, ProviderNotReadyError,
)


ProviderFactory = Callable[[], BaseProvider]
"""A factory that creates a fresh provider instance."""


class ProviderRegistry:
    """Central registry for all providers.

    Stores factory functions, not instances. Instances are created
    lazily on first get() and cached. This ensures:
    - No initialization cost at import time
    - Lifecycle is explicit (initialize/shutdown)
    """

    def __init__(self) -> None:
        # provider_type -> name -> factory
        self._factories: dict[ProviderType, dict[str, ProviderFactory]] = defaultdict(dict)
        # provider_type -> name -> instance (lazy)
        self._instances: dict[ProviderType, dict[str, BaseProvider]] = defaultdict(dict)
        # provider_type -> default name
        self._defaults: dict[ProviderType, str] = {}

    # ── Registration ──

    def register(
        self,
        provider_type: ProviderType,
        name: str,
        factory: Type[BaseProvider] | ProviderFactory,
    ) -> None:
        """Register a provider factory.

        Args:
            provider_type: LLM / EMBEDDING / VECTOR / STORAGE
            name: unique name within this type (e.g. "openai", "mock")
            factory: class (uninstantiated) or callable returning BaseProvider
        """
        # Wrap class into factory if needed
        if isinstance(factory, type):
            cls = factory
            factory = lambda: cls()  # noqa

        self._factories[provider_type][name] = factory

        # Set first registered as default
        if provider_type not in self._defaults:
            self._defaults[provider_type] = name

    def unregister(self, provider_type: ProviderType, name: str) -> bool:
        """Remove a provider registration. Shuts down instance if live.

        Returns True if the provider existed.
        """
        # Shutdown instance if alive
        instance = self._instances.get(provider_type, {}).pop(name, None)
        if instance:
            # Best-effort shutdown — don't propagate error
            try:
                import asyncio
                asyncio.get_event_loop().run_until_complete(instance.shutdown())
            except Exception:
                pass

        # Remove factory
        removed = name in self._factories.get(provider_type, {})
        self._factories.get(provider_type, {}).pop(name, None)

        # Reset default if needed
        if self._defaults.get(provider_type) == name:
            remaining = list(self._factories.get(provider_type, {}).keys())
            self._defaults[provider_type] = remaining[0] if remaining else ""

        return removed

    # ── Retrieval ──

    def get(self, provider_type: ProviderType, name: str = "") -> BaseProvider:
        """Get a provider instance (lazy-initializes if needed).

        If name is empty, returns the default provider for the type.
        """
        name = name or self._defaults.get(provider_type, "")
        if not name:
            raise ProviderNotFoundError(provider_type.value, "(no default)")

        # Return cached instance
        if provider_type in self._instances and name in self._instances[provider_type]:
            return self._instances[provider_type][name]

        # Create from factory
        factory = self._factories.get(provider_type, {}).get(name)
        if factory is None:
            raise ProviderNotFoundError(provider_type.value, name)

        instance = factory()
        self._instances[provider_type][name] = instance
        return instance

    def get_initialized(self, provider_type: ProviderType, name: str = "") -> BaseProvider:
        """Get a provider and ensure it is initialized (ready)."""
        import asyncio
        instance = self.get(provider_type, name)
        if not instance.is_available():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    raise ProviderNotReadyError(
                        instance.metadata().provider_id,
                        instance.metadata().status.value,
                    )
                loop.run_until_complete(instance.initialize())
            except RuntimeError:
                # No event loop — sync init
                loop = asyncio.new_event_loop()
                loop.run_until_complete(instance.initialize())
        return instance

    # ── Introspection ──

    def list(self, provider_type: ProviderType | None = None) -> list[str]:
        """List registered provider names. None = all types."""
        if provider_type:
            return list(self._factories.get(provider_type, {}).keys())
        result = []
        for names in self._factories.values():
            result.extend(names.keys())
        return result

    def exists(self, provider_type: ProviderType, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._factories.get(provider_type, {})

    def find_by_capability(self, capability_name: str) -> list[tuple[ProviderType, str]]:
        """Find all providers that declare a specific capability.

        NOTE: This instantiates providers briefly to check caps.
        For performance-critical paths, cache the result.
        """
        results = []
        for ptype, names in self._factories.items():
            for name in names:
                try:
                    instance = self.get(ptype, name)
                    if instance.has_capability(capability_name):
                        results.append((ptype, name))
                except Exception:
                    pass
        return results

    # ── Lifecycle ──

    def shutdown_all(self) -> None:
        """Shutdown all instantiated providers."""
        import asyncio
        for ptype, instances in self._instances.items():
            for name, instance in list(instances.items()):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        continue  # skip async shutdown in running loop
                    loop.run_until_complete(instance.shutdown())
                except Exception:
                    pass
        self._instances.clear()

    @property
    def provider_count(self) -> int:
        """Total number of registered provider factories."""
        return sum(len(n) for n in self._factories.values())

    @property
    def instance_count(self) -> int:
        """Number of lazily-initialized provider instances."""
        return sum(len(i) for i in self._instances.values())
