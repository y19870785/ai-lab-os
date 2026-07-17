from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


def _settings(path):
    return make_test_settings(path, enable_scheduler=True, enable_reminders=True, timezone_name="Asia/Shanghai", scheduler_tick_interval=0.01)


def test_agenda_default_today_utf8_json(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.get("/agenda")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert "charset=utf-8" in resp.headers["content-type"].lower()
        body = resp.json()
        assert body["view"] == "today"
        assert body["timezone"] == "Asia/Shanghai"


def test_agenda_today_with_tasks_and_reminders(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        client.post("/chat", json={"user_input": "今天下午3点提醒我联系张经理"})
        client.post("/chat", json={"user_input": "明天上午10点提醒我整理报价"})
        before = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        resp = client.get("/agenda")
        after = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        assert resp.status_code == 200
        assert before == after


def test_agenda_view_next(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.get("/agenda?view=next&window_hours=3")
        assert resp.status_code == 200
        assert resp.json()["view"] == "next"


def test_agenda_invalid_view(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.get("/agenda?view=nonexistent")
        assert resp.status_code == 400


def test_agenda_invalid_limit(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.get("/agenda?limit=200")
        assert resp.status_code == 400
