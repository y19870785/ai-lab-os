"""Protected Daily Review API contract."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock

HEADERS = {
    "X-Tenant-ID": "tenant-api",
    "X-Workspace-ID": "workspace-api",
    "X-Namespace": "namespace-api",
}


def _client(tmp_path, *, enabled: bool = True):
    settings = make_test_settings(
        tmp_path,
        enable_daily_review=enabled,
        timezone_name="UTC",
    )
    clock = MutableClock(datetime(2026, 7, 27, 12, tzinfo=UTC))
    return TestClient(create_app(settings, clock=clock))


def test_api_default_and_explicit_pages_are_structurally_identical(tmp_path):
    with _client(tmp_path) as client:
        created = client.post(
            "/work-logs",
            headers=HEADERS,
            json={
                "subject": "API fact",
                "raw_text": "API fact",
                "occurred_at": "2026-07-27T10:00:00Z",
                "timezone": "UTC",
                "status": "completed",
            },
        )
        assert created.status_code == 200

        default = client.get(
            "/daily-review",
            params={"date": "today"},
            headers=HEADERS,
        )
        explicit = client.get(
            "/daily-review",
            params={"date": "today", "limit": 50, "offset": 0},
            headers=HEADERS,
        )

    assert default.status_code == explicit.status_code == 200
    assert default.json() == explicit.json()
    body = default.json()
    assert body["workspace"] == {
        "tenant_id": "tenant-api",
        "workspace_id": "workspace-api",
        "namespace": "namespace-api",
    }
    assert body["completed"]["items"][0]["source_id"] == created.json()["id"]
    assert body["page"] == {
        "count": 1,
        "total_count": 1,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }


def test_api_today_and_yesterday_use_local_date_contract(tmp_path):
    with _client(tmp_path) as client:
        today = client.get("/daily-review", params={"date": "today"})
        yesterday = client.get("/daily-review", params={"date": "yesterday"})

    assert today.status_code == yesterday.status_code == 200
    assert today.json()["review_date"] == "2026-07-27"
    assert yesterday.json()["review_date"] == "2026-07-26"
    assert today.json()["as_of"] == yesterday.json()["as_of"]


def test_api_invalid_pagination_uses_daily_review_failure_before_sources(tmp_path):
    with _client(tmp_path) as client:
        system = client.app.state.system
        original = system.work_log_service.list
        calls = 0

        async def spy(*args, **kwargs):
            nonlocal calls
            calls += 1
            return await original(*args, **kwargs)

        system.work_log_service.list = spy
        for params in (
            {"date": "today", "limit": 0},
            {"date": "today", "limit": 101},
            {"date": "today", "offset": -1},
        ):
            response = client.get("/daily-review", params=params)
            assert response.status_code == 400
            assert response.json()["code"] == "daily_review.query_invalid"
        assert calls == 0


def test_api_invalid_date_and_source_failure_are_sanitized(tmp_path):
    with _client(tmp_path) as client:
        invalid = client.get("/daily-review", params={"date": "tomorrow"})
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "daily_review.date_invalid"

        async def fail(*args, **kwargs):
            raise RuntimeError("SELECT private FROM C:/secret/review.db")

        client.app.state.system.work_log_service.list = fail
        failed = client.get("/daily-review", params={"date": "today"})

    assert failed.status_code == 503
    assert failed.json()["code"] == "daily_review.source_failed"
    assert failed.json()["details"] == {
        "source": "work_log",
        "upstream_code": "work_log.unhandled_failure",
        "upstream_category": "internal",
    }
    assert "secret" not in failed.text.lower()
    assert "select" not in failed.text.lower()


def test_api_disabled_and_not_configured_are_distinct(tmp_path):
    with _client(tmp_path / "disabled", enabled=False) as client:
        disabled = client.get("/daily-review", params={"date": "today"})
    assert disabled.status_code == 503
    assert disabled.json()["code"] == "daily_review.unavailable"

    with _client(tmp_path / "missing") as client:
        client.app.state.system.daily_review = None
        missing = client.get("/daily-review", params={"date": "today"})
    assert missing.status_code == 503
    assert missing.json()["code"] == "daily_review.unavailable"
