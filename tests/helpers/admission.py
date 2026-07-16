"""Explicit permissive admission used only by standalone component tests."""

from contextlib import contextmanager
from typing import Iterator


class PermissiveTestAdmission:
    """Allow work in tests that intentionally construct components without a system."""

    def ensure_accepting_work(self) -> None:
        return None

    @contextmanager
    def admit(self) -> Iterator[None]:
        yield


PERMISSIVE_TEST_ADMISSION = PermissiveTestAdmission()
