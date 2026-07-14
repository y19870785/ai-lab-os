"""系统组合与生命周期异常。"""


class SystemError(Exception):
    """System composition base error."""


class SystemInitializationError(SystemError):
    """Raised when the system cannot reach the ready state."""


class SystemShutdownError(SystemError):
    """Raised when one or more resources fail to shut down."""


class ProviderNotConfiguredError(SystemInitializationError):
    """Raised when provider settings are incomplete or ambiguous."""


class ServiceUnavailableError(SystemError):
    """Raised when a required service is not available."""


class ServiceDisabledError(ServiceUnavailableError):
    """Raised when a service is intentionally disabled."""
