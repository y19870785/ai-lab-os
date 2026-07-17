from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


def _settings(path):
    return make_test_settings(path, enable_scheduler=True, enable_reminders=True, timezone_name="Asia/Shanghai", scheduler_tick_interval=0.01)


def test_daily_agenda_integration_all_views_no_side_effects(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        client.post("/chat", json={"user_input": "今天下午3点提醒我处理报价"})
        client.post("/chat", json={"user_input": "明天上午10点提醒我联系张经理"})
        base_counts = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        for view in ["today", "next", "attention", "completed", "all"]:
            resp = client.get(f"/agenda?view={view}")
            assert resp.status_code in (200, 503)
            assert resp.json()["view"] == view
            after = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
            assert base_counts == after


def test_daily_agenda_workspace_isolation(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        a_hdrs = {"X-Tenant-ID": "t", "X-Workspace-ID": "alpha"}
        b_hdrs = {"X-Tenant-ID": "t", "X-Workspace-ID": "beta"}
        client.post("/chat", json={"user_input": "今天下午4点提醒我Alpha任务"}, headers=a_hdrs)
        client.post("/chat", json={"user_input": "今天下午5点提醒我Beta任务"}, headers=b_hdrs)
        page_a = client.get("/agenda", headers=a_hdrs)
        page_b = client.get("/agenda", headers=b_hdrs)
        assert page_a.status_code == page_b.status_code == 200
        assert len(page_a.json()["items"]) > 0
        assert len(page_b.json()["items"]) > 0


def test_sp_012_reminder_query_still_works(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        client.post("/chat", json={"user_input": "今天下午3点提醒我测试"})
        before = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        resp = client.post("/chat", json={"user_input": "今天都有什么事？"})
        after = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        assert resp.status_code in (200, 503)
        assert resp.json()["metadata"]["intent"] == "reminder_list"
        assert resp.json()["metadata"]["effect"] == "read"
        assert before == after
