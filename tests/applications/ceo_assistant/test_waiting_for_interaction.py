import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.intent import IntentDecision, IntentEffect, decide_intent
from applications.ceo_assistant.waiting_for_errors import WaitingForUserErrorPresenter
from applications.ceo_assistant.waiting_for_intent import parse_waiting_for_time
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system import make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 23, 1, 0, tzinfo=timezone.utc)


def _settings(path):
    return make_test_settings(path, timezone_name="Asia/Shanghai")


def _counts(system):
    async def collect():
        workspace = WorkspaceKey()
        inbox = await system.inbox_service.list(
            workspace_key=workspace, status="all", limit=200
        )
        waiting = await system.waiting_for_service.list(
            workspace_key=workspace, view="all", limit=200
        )
        event_count = 0
        for item in waiting.items:
            event_count += len((await system.waiting_for_service.list_events(
                workspace_key=workspace, waiting_for_id=item.id
            )).items)
        return len(inbox.items), len(waiting.items), event_count

    return asyncio.run(collect())


def test_waiting_for_intent_effect_contract_is_explicit():
    expected = {
        "查看等待事项": ("waiting_for_list", IntentEffect.READ),
        "查看等待事项 wf_demo": ("waiting_for_detail", IntentEffect.READ),
        "查看 wf_demo 的催办历史": ("waiting_for_history", IntentEffect.READ),
        "等张经理回复蜂蜡检测方案": ("waiting_for_capture", IntentEffect.WRITE),
        "把 inbox_demo 整理成等待事项：等待张经理回复方案，明天下午三点再看": (
            "waiting_for_confirm",
            IntentEffect.WRITE,
        ),
        "催办 wf_demo：已联系": ("waiting_for_follow_up", IntentEffect.WRITE),
        "把 wf_demo 延后到明天下午三点：出差": (
            "waiting_for_snooze",
            IntentEffect.WRITE,
        ),
        "解决 wf_demo：已回复": ("waiting_for_resolve", IntentEffect.WRITE),
        "取消 wf_demo：不再需要": ("waiting_for_cancel", IntentEffect.WRITE),
        "重新打开 wf_demo：补充材料": ("waiting_for_reopen", IntentEffect.WRITE),
    }
    for text, pair in expected.items():
        decision = decide_intent(text)
        assert (decision.intent, decision.effect) == pair
        CEOAssistant._assert_effect_contract(decision)
        wrong = IntentEffect.WRITE if decision.effect == IntentEffect.READ else IntentEffect.READ
        with pytest.raises(RuntimeError):
            CEOAssistant._assert_effect_contract(
                IntentDecision(decision.intent, 1.0, wrong)
            )


@pytest.mark.parametrize(
    "text",
    (
        "取消任务 task_demo",
        "解决这个问题怎么做",
        "把会议延后到明天",
        "取消今天的安排",
        "重新打开这个项目",
        "催办客户尽快付款",
    ),
)
def test_non_waiting_for_language_is_not_hijacked_by_lifecycle_intents(text):
    lifecycle_intents = {
        "waiting_for_follow_up",
        "waiting_for_snooze",
        "waiting_for_resolve",
        "waiting_for_cancel",
        "waiting_for_reopen",
    }

    assert decide_intent(text).intent not in lifecycle_intents


def test_waiting_for_time_parser_reuses_supported_subset_and_fails_closed():
    clock = MutableClock(NOW)
    parsed = parse_waiting_for_time("明天下午三点再看", "Asia/Shanghai", clock)
    assert parsed == datetime(2026, 7, 24, 7, 0, tzinfo=timezone.utc)
    assert parse_waiting_for_time(
        "2026-07-25T09:30:00+08:00", "Asia/Shanghai", clock
    ) == datetime(2026, 7, 25, 1, 30, tzinfo=timezone.utc)
    with pytest.raises(FailureException) as exc:
        parse_waiting_for_time("下周有空时", "Asia/Shanghai", clock)
    assert exc.value.failure.code == "waiting_for.time_unsupported"


@pytest.mark.parametrize(
    ("code", "expected_message"),
    (
        ("inbox.not_found", "未找到该 Inbox 记录，请检查 Inbox ID。"),
        (
            "inbox.workspace_mismatch",
            "当前 Workspace 无权访问或确认该 Inbox 记录。",
        ),
        (
            "inbox.already_resolved",
            "该 Inbox 已完成转换，不能再次转换为其他类型。",
        ),
        (
            "waiting_for.resolve.conflict",
            "解决操作发生状态或 revision 冲突；未自动重试。",
        ),
    ),
)
def test_waiting_for_presenter_changes_only_message(code, expected_message):
    failure = FailureInfo(
        code=code,
        category=ErrorCategory.CONFLICT,
        message="machine message",
        component="waiting_for",
        operation="resolve",
        retryable=False,
        trace_id="trace-1",
        details={"revision": 3},
    )
    presented = WaitingForUserErrorPresenter.present(failure)
    assert presented.message == expected_message
    assert presented.model_copy(update={"message": failure.message}) == failure


def test_cancel_task_does_not_read_or_write_waiting_for(tmp_path, monkeypatch):
    with TestClient(create_app(_settings(tmp_path), clock=MutableClock(NOW))) as client:
        service = client.app.state.system.waiting_for_service

        async def unexpected_waiting_for_access(*args, **kwargs):
            raise AssertionError("Waiting-For service must not be accessed")

        for name in (
            "list",
            "get",
            "record_follow_up",
            "snooze",
            "resolve",
            "cancel",
            "reopen",
        ):
            monkeypatch.setattr(service, name, unexpected_waiting_for_access)

        response = client.post("/chat", json={"user_input": "取消任务 task_x"})

        assert response.json()["code"] == "application.ceo_assistant.execute_failed"
        assert "候选等待事项" not in response.text


def test_waiting_for_confirm_errors_are_presented_in_chinese(tmp_path):
    clock = MutableClock(NOW)
    confirmation = (
        "把 {item_id} 整理成等待事项："
        "等待张经理回复蜂蜡检测方案，明天下午三点再看"
    )
    alpha = {"X-Workspace-ID": "alpha"}
    beta = {"X-Workspace-ID": "beta"}

    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        missing = client.post(
            "/chat",
            json={"user_input": confirmation.format(item_id="inbox_missing")},
        )

        scoped_item = client.post(
            "/inbox",
            json={"content": "跨 Workspace 等待确认"},
            headers=alpha,
        ).json()
        mismatch = client.post(
            "/chat",
            json={
                "user_input": confirmation.format(item_id=scoped_item["id"])
            },
            headers=beta,
        )

        resolved_item = client.post(
            "/inbox",
            json={"content": "已转换等待确认"},
            headers=alpha,
        ).json()
        client.post(
            f"/inbox/{resolved_item['id']}/resolve/note",
            headers=alpha,
        )
        already_resolved = client.post(
            "/chat",
            json={
                "user_input": confirmation.format(item_id=resolved_item["id"])
            },
            headers=alpha,
        )

        assert missing.status_code == 404
        assert missing.json()["code"] == "inbox.not_found"
        assert missing.json()["message"] == "未找到该 Inbox 记录，请检查 Inbox ID。"

        assert mismatch.status_code == 403
        assert mismatch.json()["code"] == "inbox.workspace_mismatch"
        assert mismatch.json()["message"] == (
            "当前 Workspace 无权访问或确认该 Inbox 记录。"
        )

        assert already_resolved.status_code == 409
        assert already_resolved.json()["code"] == "inbox.already_resolved"
        assert already_resolved.json()["message"] == (
            "该 Inbox 已完成转换，不能再次转换为其他类型。"
        )
        assert already_resolved.json()["details"] == {
            "claim_state": "completed",
            "claimed_type": "note",
            "resolved_type": "note",
            "resolved_target_id": None,
            "target_id": None,
        }


def test_waiting_for_capture_confirm_read_and_lifecycle_are_deterministic(tmp_path):
    clock = MutableClock(NOW)
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        before = _counts(client.app.state.system)
        capture = client.post(
            "/chat", json={"user_input": "等张经理回复蜂蜡检测方案"}
        )
        captured = capture.json()["metadata"]["inbox_item"]
        after_capture = _counts(client.app.state.system)

        assert capture.status_code == 200
        assert captured["suggested_type"] == "waiting_for"
        assert after_capture == (before[0] + 1, before[1], before[2])
        assert captured["id"] in capture.json()["answer"]

        confirm_text = (
            f"把 {captured['id']} 整理成等待事项："
            "等待张经理回复蜂蜡检测方案，明天下午三点再看"
        )
        confirm = client.post("/chat", json={"user_input": confirm_text})
        body = confirm.json()
        waiting_for_id = body["metadata"]["waiting_for"]["id"]
        after_confirm = _counts(client.app.state.system)

        assert confirm.status_code == 200
        assert waiting_for_id.startswith("wf_inbox_")
        assert body["metadata"]["event"]["event_type"] == "created"
        assert after_confirm == (before[0] + 1, before[1] + 1, before[2] + 1)

        list_before = _counts(client.app.state.system)
        listed = client.post("/chat", json={"user_input": "查看等待事项"})
        detail = client.post(
            "/chat", json={"user_input": f"查看等待事项 {waiting_for_id}"}
        )
        history = client.post(
            "/chat", json={"user_input": f"查看 {waiting_for_id} 的催办历史"}
        )
        assert _counts(client.app.state.system) == list_before
        assert all(response.status_code == 200 for response in (listed, detail, history))
        assert waiting_for_id in listed.json()["answer"]

        fuzzy = client.post(
            "/chat", json={"user_input": "解决蜂蜡检测方案：已经收到回复"}
        )
        assert fuzzy.status_code == 200
        assert fuzzy.json()["metadata"]["intent"] == "chat"
        assert "候选等待事项" not in fuzzy.json()["answer"]
        assert _counts(client.app.state.system) == list_before

        follow_up = client.post(
            "/chat", json={"user_input": f"催办 {waiting_for_id}：已通过微信联系"}
        )
        snoozed = client.post(
            "/chat",
            json={
                "user_input": f"把 {waiting_for_id} 延后到明天下午四点：对方出差"
            },
        )
        resolved = client.post(
            "/chat", json={"user_input": f"解决 {waiting_for_id}：已经收到回复"}
        )
        reopened = client.post(
            "/chat", json={"user_input": f"重新打开 {waiting_for_id}：还需补充材料"}
        )
        cancelled = client.post(
            "/chat", json={"user_input": f"取消 {waiting_for_id}：客户不再需要"}
        )
        assert all(
            response.status_code == 200
            for response in (follow_up, snoozed, resolved, reopened, cancelled)
        )
        assert follow_up.json()["metadata"]["event"]["event_type"] == "followed_up"
        assert snoozed.json()["metadata"]["event"]["event_type"] == "snoozed"
        assert resolved.json()["metadata"]["item"]["status"] == "resolved"
        assert reopened.json()["metadata"]["item"]["status"] == "open"
        assert cancelled.json()["metadata"]["item"]["status"] == "cancelled"
        assert _counts(client.app.state.system)[2] == before[2] + 6


def test_waiting_for_revision_conflict_is_not_retried(tmp_path, monkeypatch):
    clock = MutableClock(NOW)
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        created = client.post(
            "/waiting-for",
            json={
                "subject": "等待回复",
                "waiting_on": "张经理",
                "next_review_at": (NOW + timedelta(days=1)).isoformat(),
                "timezone": "Asia/Shanghai",
            },
        ).json()["item"]
        service = client.app.state.system.waiting_for_service
        calls = 0

        async def conflict(**_values):
            nonlocal calls
            calls += 1
            raise FailureException(FailureInfo(
                code="waiting_for.resolve.conflict",
                category=ErrorCategory.CONFLICT,
                message="stale revision",
                component="waiting_for",
                operation="resolve",
            ))

        monkeypatch.setattr(service, "resolve", conflict)
        before = _counts(client.app.state.system)
        response = client.post(
            "/chat",
            json={"user_input": f"解决 {created['id']}：已经收到回复"},
        )

        assert response.status_code == 409
        assert response.json()["code"] == "waiting_for.resolve.conflict"
        assert calls == 1
        assert _counts(client.app.state.system) == before


def test_waiting_for_agenda_label_and_chat_fallback_have_no_side_effect(tmp_path):
    clock = MutableClock(NOW)
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        created = client.post(
            "/waiting-for",
            json={
                "subject": "蜂蜡检测方案",
                "waiting_on": "张经理",
                "context": "不得出现在 Agenda",
                "next_review_at": NOW.isoformat(),
                "timezone": "Asia/Shanghai",
            },
        ).json()
        agenda = client.post(
            "/chat", json={"user_input": "有哪些需要注意的事项"}
        )
        before_chat = _counts(client.app.state.system)
        fallback = client.post("/chat", json={"user_input": "你好，随便聊聊"})

        assert agenda.status_code == fallback.status_code == 200
        assert "等待事项" in agenda.json()["answer"]
        assert created["item"]["id"] in agenda.json()["answer"]
        assert "张经理" in agenda.json()["answer"]
        assert "不得出现在 Agenda" not in agenda.json()["answer"]
        assert _counts(client.app.state.system) == before_chat
