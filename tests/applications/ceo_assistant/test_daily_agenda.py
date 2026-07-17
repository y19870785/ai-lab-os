import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock
from applications.ceo_assistant.intent import IntentDecision, IntentEffect
from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.intent import IntentDecision, IntentEffect
from applications.ceo_assistant.application import CEOAssistant


def _settings(path):
    return make_test_settings(path, enable_scheduler=True, enable_reminders=True, timezone_name="Asia/Shanghai", scheduler_tick_interval=0.01)


def test_daily_agenda_intent_read_only_no_mock_noise(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        before = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        resp = client.post("/chat", json={"user_input": "今天有什么安排？"})
        after = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["intent"] == "daily_agenda"
        assert meta["effect"] == "read"
        assert before == after
        assert "MOCK MODE" not in resp.json()["answer"]
        assert "API_KEY" not in resp.json()["answer"]


def test_daily_agenda_next_three_hours(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.post("/chat", json={"user_input": "接下来三个小时有什么安排？"})
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["intent"] == "daily_agenda"
        assert meta["effect"] == "read"


def test_daily_agenda_attention(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.post("/chat", json={"user_input": "有哪些需要注意的事项？"})
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["intent"] == "daily_agenda"
        assert meta["effect"] == "read"


def test_daily_agenda_completed(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        resp = client.post("/chat", json={"user_input": "今天已经完成了什么？"})
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["intent"] == "daily_agenda"
        assert meta["effect"] == "read"


def test_sp_012_reminder_query_still_reminder_list(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        client.post("/chat", json={"user_input": "今天下午3点提醒我测试"})
        before = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        resp = client.post("/chat", json={"user_input": "今天都有什么事？"})
        after = (len(client.get("/tasks").json()), client.get("/reminders?limit=100").json()["count"])
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["intent"] == "reminder_list"
        assert meta["effect"] == "read"
        assert before == after


def test_effect_contract_daily_agenda_accepts_read():
    decision = IntentDecision(intent="daily_agenda", effect=IntentEffect.READ, confidence=1.0)
    CEOAssistant._assert_effect_contract(decision)

def test_effect_contract_daily_agenda_rejects_write():
    decision = IntentDecision(intent="daily_agenda", effect=IntentEffect.WRITE, confidence=1.0)
    try:
        CEOAssistant._assert_effect_contract(decision)
        rejected = False
    except RuntimeError:
        rejected = True
    assert rejected, "daily_agenda + WRITE must be rejected"

def test_effect_contract_reminder_list_still_read():
    decision = IntentDecision(intent="reminder_list", effect=IntentEffect.READ, confidence=1.0)
    CEOAssistant._assert_effect_contract(decision)


def test_effect_contract_daily_agenda_accepts_read():
    decision = IntentDecision(intent="daily_agenda", effect=IntentEffect.READ, confidence=1.0)
    CEOAssistant._assert_effect_contract(decision)

def test_effect_contract_daily_agenda_rejects_write():
    decision = IntentDecision(intent="daily_agenda", effect=IntentEffect.WRITE, confidence=1.0)
    try:
        CEOAssistant._assert_effect_contract(decision)
        rejected = False
    except RuntimeError:
        rejected = True
    assert rejected, "daily_agenda + WRITE must be rejected"

def test_effect_contract_reminder_list_still_read():
    decision = IntentDecision(intent="reminder_list", effect=IntentEffect.READ, confidence=1.0)
    CEOAssistant._assert_effect_contract(decision)
