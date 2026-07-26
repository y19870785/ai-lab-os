"""Work Log repository and domain boundary exceptions."""


class WorkLogError(RuntimeError):
    """Base exception for Work Log failures."""


class WorkLogNotConfiguredError(WorkLogError):
    """Raised when the canonical Work Log service is unavailable."""


class WorkLogNotFoundError(WorkLogError):
    """Raised when no Work Log matches a requested identity."""


class WorkLogWorkspaceMismatchError(WorkLogError):
    """Raised when an identity exists outside the request workspace."""


class WorkLogIdInvalidError(WorkLogError):
    """Raised for unsupported public Work Log identifier shapes."""


class WorkLogConflictError(WorkLogError):
    """Raised when insert-only identity ownership conflicts."""


class WorkLogRepositoryError(WorkLogError):
    """Raised when SQLite persistence cannot complete safely."""


class WorkLogLegacyProjectionError(WorkLogRepositoryError):
    """Raised when a Work Log row cannot be projected without guessing."""

    def __init__(self, message: str, *, row_digest: str, field: str) -> None:
        super().__init__(message)
        self.row_digest = row_digest
        self.field = field
