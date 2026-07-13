import pytest
from datetime import datetime, timezone, timedelta
from core.scheduler.triggers import TriggerEngine
from core.scheduler.models import Trigger, TriggerType


class TestTriggerEngine:
    def test_should_fire_true(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60, next_run_at=past)
        assert TriggerEngine.should_fire(t) is True

    def test_should_fire_false(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60, next_run_at=future)
        assert TriggerEngine.should_fire(t) is False

    def test_should_fire_no_next(self):
        t = Trigger(trigger_type=TriggerType.MANUAL)
        assert TriggerEngine.should_fire(t) is False

    def test_compute_next_interval(self):
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60)
        next_run = TriggerEngine.compute_next(t)
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)

    def test_compute_next_one_shot(self):
        dt = datetime.now(timezone.utc) + timedelta(hours=2)
        t = Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=dt)
        assert TriggerEngine.compute_next(t) == dt

    def test_compute_next_manual(self):
        t = Trigger(trigger_type=TriggerType.MANUAL)
        assert TriggerEngine.compute_next(t) is None

    def test_compute_next_cron(self):
        t = Trigger(trigger_type=TriggerType.CRON, cron_expression="*/5 * * * *")
        next_run = TriggerEngine.compute_next(t)
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)

    def test_validate_cron_valid(self):
        t = Trigger(trigger_type=TriggerType.CRON, cron_expression="*/5 * * * *")
        assert TriggerEngine.validate(t) is True

    def test_validate_cron_invalid(self):
        t = Trigger(trigger_type=TriggerType.CRON, cron_expression="bad")
        assert TriggerEngine.validate(t) is False

    def test_validate_interval(self):
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=30)
        assert TriggerEngine.validate(t) is True

    def test_validate_interval_zero(self):
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=0)
        assert TriggerEngine.validate(t) is False
