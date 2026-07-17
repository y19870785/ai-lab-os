"""Regression tests for parse_iso_timestamp compatibility."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from core.time_utils import parse_iso_timestamp


class TestParseIsoTimestamp:
    def test_parse_Z_suffix(self):
        """Pydantic JSON serialization produces Z suffix on Windows."""
        result = parse_iso_timestamp("2026-07-17T16:09:01.651851Z")
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(0)

    def test_parse_plus_0000_offset(self):
        """Python isoformat() for UTC produces +00:00."""
        result = parse_iso_timestamp("2026-07-17T16:09:01.651851+00:00")
        assert result.tzinfo is not None
        assert result == datetime(2026, 7, 17, 16, 9, 1, 651851, tzinfo=timezone.utc)

    def test_parse_non_utc_offset(self):
        """Other legal offsets must be preserved."""
        result = parse_iso_timestamp("2026-07-17T20:09:01+04:00")
        assert result.utcoffset() == timedelta(hours=4)

    def test_parse_without_microseconds(self):
        """Timestamp without fractional seconds must work."""
        result = parse_iso_timestamp("2026-07-17T16:09:01+00:00")
        assert result.tzinfo is not None

    def test_reject_naive_datetime(self):
        """Naive datetime (no offset) must raise ValueError."""
        with pytest.raises(ValueError, match="Naive datetime"):
            parse_iso_timestamp("2026-07-17T16:09:01")

    def test_reject_empty_string(self):
        """Empty string must raise ValueError."""
        with pytest.raises(ValueError, match="Empty"):
            parse_iso_timestamp("")

    def test_reject_invalid_format(self):
        """Garbage input must raise ValueError."""
        with pytest.raises(ValueError):
            parse_iso_timestamp("not-a-date")
