"""Provider Layer exceptions."""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all provider errors."""
    pass


class ProviderNotFoundError(ProviderError):
    """No provider registered for the requested type/name."""
    def __init__(self, provider_type: str, name: str = "default") -> None:
        super().__init__(f"Provider not found: {provider_type}/{name}")
        self.provider_type = provider_type
        self.name = name


class ProviderNotReadyError(ProviderError):
    """Provider is registered but not in READY state."""
    def __init__(self, provider_id: str, status: str) -> None:
        super().__init__(f"Provider {provider_id} is {status}, not READY")
        self.provider_id = provider_id
        self.status = status


class ProviderOperationError(ProviderError):
    """A provider operation failed (after retries)."""
    def __init__(self, provider_id: str, operation: str, detail: str = "") -> None:
        super().__init__(f"{provider_id}.{operation} failed: {detail}")
        self.provider_id = provider_id
        self.operation = operation


class ProviderConfigurationError(ProviderError):
    """Invalid provider configuration."""
    pass


class ProviderTimeoutError(ProviderError):
    """Provider operation timed out."""
    pass
