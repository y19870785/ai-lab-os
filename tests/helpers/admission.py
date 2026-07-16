"""Explicit permissive admission used only by standalone component tests."""

import asyncio
from contextlib import contextmanager
from typing import Any, Coroutine, Iterator, TypeVar


T = TypeVar("T")


class PermissiveTestAdmission:
    """Allow work in tests that intentionally construct components without a system."""

    def ensure_accepting_work(self) -> None:
        return None

    @contextmanager
    def admit(self) -> Iterator[None]:
        yield

    def spawn_accepted_task(
        self,
        coroutine: Coroutine[Any, Any, T],
        *,
        name: str | None = None,
    ) -> asyncio.Task[T]:
        return asyncio.create_task(coroutine, name=name)


PERMISSIVE_TEST_ADMISSION = PermissiveTestAdmission()
