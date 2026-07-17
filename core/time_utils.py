"""ISO 8601 timestamp parsing with cross-Python-version compatibility.

Python 3.10 datetime.fromisoformat() does not accept the 'Z' suffix.
Pydantic serializes UTC datetimes as 'Z' in JSON mode.
This module provides a single canonical parse entry-point.
"""

from __future__ import annotations

from datetime import datetime


def parse_iso_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime.

    Compatible with:
    - ``2026-07-17T16:09:01.651851Z``       (Pydantic JSON serialization)
    - ``2026-07-17T16:09:01.651851+00:00``  (Python isoformat)
    - ``2026-07-17T16:09:01+00:00``         (without microseconds)
    - Any other valid ISO 8601 offset string

    Raises ValueError if the input is not a valid ISO 8601 string with
    a timezone offset or Z suffix.
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError("Empty timestamp string")

    # Python 3.10 fromisoformat() does not support 'Z'
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    # Contract: reject naive datetimes
    if parsed.tzinfo is None:
        raise ValueError(
            f"Naive datetime not allowed: {value!r}. "
            "Timestamp must include timezone offset (e.g. +00:00 or Z)."
        )

    return parsed
