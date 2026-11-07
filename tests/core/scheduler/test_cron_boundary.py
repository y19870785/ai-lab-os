"""Do not skip the first future minute when it already matches the step."""

from datetime import datetime

import pytest

from core.scheduler.models import Trigger, TriggerType
from core.scheduler.triggers import TriggerEngine


@pytest.mark.parametrize(("expression", "now", "expected"), [
    ("*/5 * * * *", "2000-01-01T12:04:59+00:00", "2000-01-01T12:05:00+00:00"),
    ("*/5 * * * *", "2000-01-01T12:05:00+00:00", "2000-01-01T12:10:00+00:00"),
    ("*/1 * * * *", "2000-01-01T12:04:00+00:00", "2000-01-01T12:05:00+00:00"),
    ("*/15 * * * *", "2000-01-01T23:59:59.999999+00:00", "2000-01-02T00:00:00+00:00"),
    ("* */2 * * *", "2000-01-01T13:59:59+00:00", "2000-01-01T14:00:00+00:00"),
    ("* */2 * * *", "2000-01-01T14:00:00+00:00", "2000-01-01T14:01:00+00:00"),
    ("* */1 * * *", "2000-01-01T12:04:59+00:00", "2000-01-01T12:05:00+00:00"),
    ("*/5 */2 * * *", "2000-01-01T13:59:59+00:00", "2000-01-01T14:00:00+00:00"),
    ("*/5 */2 * * *", "2000-01-01T23:59:59+00:00", "2000-01-02T00:00:00+00:00"),
])
def test_aligned_future_boundary_is_not_skipped(expression, now, expected):
    instant = datetime.fromisoformat(now)
    trigger = Trigger(trigger_type=TriggerType.CRON, cron_expression=expression)
    result = TriggerEngine.compute_next(trigger, instant)
    assert result == datetime.fromisoformat(expected)
    assert result > instant
    assert result.second == result.microsecond == 0
