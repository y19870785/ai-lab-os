"""Observation must not change persistence arguments, results, or failures."""

import json
from datetime import UTC, datetime

import pytest

from core.scheduler.persistence import SchedulerPersistence
from tests.helpers.scheduler_timeline import SchedulerTimeline, TimelinePersistence


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [True, False])
async def test_renew_observation_preserves_call_and_result(monkeypatch, tmp_path, result):
    calls = []
    now = datetime(2000, 1, 1, tzinfo=UTC)

    async def renew(self, *args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(SchedulerPersistence, "renew_claim", renew)
    timeline = SchedulerTimeline()
    persistence = TimelinePersistence(tmp_path / "unused.db", timeline, "probe")
    assert await persistence.renew_claim("job", "secret-test-token", now, now=now) is result
    assert calls == [(("job", "secret-test-token", now), {"now": now})]
    assert [item["event"] for item in timeline.events] == ["renew.begin", "renew.end"]
    assert timeline.events[-1]["renewed"] is result
    assert "secret-test-token" not in json.dumps(timeline.events)
    assert not (tmp_path / "unused.db").exists()


@pytest.mark.asyncio
async def test_observation_preserves_original_exception(monkeypatch, tmp_path):
    original = RuntimeError("secret-test-message")

    async def renew(self, *args, **kwargs):
        raise original

    monkeypatch.setattr(SchedulerPersistence, "renew_claim", renew)
    timeline = SchedulerTimeline()
    persistence = TimelinePersistence(tmp_path / "unused.db", timeline, "probe")
    with pytest.raises(RuntimeError) as caught:
        await persistence.renew_claim("job", "secret-test-token", datetime.now(UTC))
    assert caught.value is original
    assert timeline.events[-1]["event"] == "renew.error"
    assert timeline.events[-1]["error_type"] == "RuntimeError"
    assert "secret-test" not in json.dumps(timeline.events)


@pytest.mark.asyncio
async def test_timeline_is_bounded_and_reports_dropped_events(tmp_path):
    timeline = SchedulerTimeline(limit=2)
    for _ in range(5):
        timeline.record("sample")
    artifact = tmp_path / "timeline.json"
    timeline.save(artifact)
    result = json.loads(artifact.read_text(encoding="utf-8"))
    assert result["schema_version"] == 1
    assert len(result["events"]) == 2
    assert result["dropped"] == 3
    assert result["events"][1]["monotonic"] >= result["events"][0]["monotonic"]
