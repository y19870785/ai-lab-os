"""Exceptions carrying the shared FailureInfo contract."""

from core.errors.models import FailureInfo


class FailureException(Exception):
    """Raised when a runtime must propagate an already classified failure."""

    def __init__(self, failure: FailureInfo):
        super().__init__(failure.message)
        self.failure = failure
