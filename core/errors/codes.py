"""Shared error and runtime status enums for AI-Lab."""

from enum import Enum


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CONFLICT = "conflict"
    DEPENDENCY_FAILURE = "dependency_failure"
    EXECUTION_FAILURE = "execution_failure"
    PERSISTENCE_FAILURE = "persistence_failure"
    PERMISSION_DENIED = "permission_denied"
    UNAUTHENTICATED = "unauthenticated"
    RATE_LIMITED = "rate_limited"
    INTERNAL = "internal"


class ErrorSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuntimeStatus(str, Enum):
    OK = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    NOT_INITIALIZED = "not_initialized"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
