"""Repository boundary exceptions for Inbox persistence."""


class InboxRepositoryError(RuntimeError):
    """Base class for Inbox repository failures."""


class InboxItemNotFoundError(InboxRepositoryError):
    """Raised when no item exists for the requested identifier."""


class InboxWorkspaceMismatchError(InboxRepositoryError):
    """Raised when an identifier exists outside the requested workspace."""


class InboxRevisionConflictError(InboxRepositoryError):
    """Raised when an optimistic update observes a stale revision."""


class InboxResolutionClaimNotFoundError(InboxRepositoryError):
    """Raised when an Inbox item has no durable resolution claim."""


class InboxResolutionClaimConflictError(InboxRepositoryError):
    """Raised when a durable claim cannot perform the requested transition."""
