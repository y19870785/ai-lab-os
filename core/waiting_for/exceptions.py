"""Repository boundary exceptions for canonical Waiting-For persistence."""


class WaitingForPersistenceError(RuntimeError):
    """Raised when Waiting-For persistence cannot complete safely."""


class WaitingForNotFoundError(WaitingForPersistenceError):
    """Raised when no item exists for the requested identifier."""


class WaitingForWorkspaceMismatchError(WaitingForPersistenceError):
    """Raised internally when an identifier belongs to another workspace."""


class WaitingForConflictError(WaitingForPersistenceError):
    """Raised for duplicate IDs, invalid state, or stale revisions."""
