"""Explicit mutable clock for deterministic time-based tests."""

from __future__ import annotations

from datetime import datetime, timedelta


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta
