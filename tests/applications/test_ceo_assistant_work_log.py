"""CEO Assistant Work Log create/query boundary tests."""

import json
from datetime import UTC, datetime

import pytest

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.intent import IntentEffect, decide_intent
from applications.ceo_assistant.work_log_intent import parse_work_log_query
from applications.models import ApplicationRequest
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system import create_system, make_test_settings
from core.work_log import WorkLogStatus, WorkLogUserErrorPresenter
from core.work_log.errors import (
    WorkLogLegacyProjectionError,
    WorkLogRepositoryError,
)
from core.workspace.models import WorkspaceKey
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from tests.helpers.clock import MutableClock

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)


def test_work_log_intent_effects_are_narrow():
    assert decide_intent("记录：完成蜂蜡报价").effect == IntentEffect.WRITE
    assert decide_intent("查看今天的工作记录").effect == IntentEffect.READ
    assert decide_intent("查看标签为蜂蜡的工作记录").effect == IntentEffect.READ


@pytest.mark.asyncio
async def test_create_then_today_tag_status_and_id_queries_are_read_only(tmp_path):
    system = await create_system(
        make_test_settings(tmp_path, timezone_name="Asia/Shanghai"),
        clock=MutableClock(NOW),
    )
    await system.start()
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        created = await system.application_runtime.execute(
            ApplicationRequest(
                application_name="ceo-assistant",
                user_input="记录：今天和张经理确认了蜂蜡报价",
                workspace_key=workspace,
            )
        )
        identifier = created.metadata["id"]
        with system.database_manager.lease("episodic") as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM episodic_memories"
            ).fetchone()[0]

        for query in (
            "查看今天的工作记录",
            f"查看工作记录 {identifier}",
            "查看张经理相关的工作记录",
            "查看标签为蜂蜡的工作记录",
            "查看状态为已完成的工作记录",
            "查看 2026-07-20 到 2026-07-23 的工作记录",
        ):
            response = await system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input=query,
                    workspace_key=workspace,
                )
            )
            assert response.status == "ok"
            assert response.metadata["count"] >= 1

        with system.database_manager.lease("episodic") as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM episodic_memories"
            ).fetchone()[0]
        assert after == before
    finally:
        await system.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "查看状态为已取消的工作记录",
        "查看状态为未知的工作记录",
        "查看状态为的工作记录",
    ],
)
async def test_unknown_status_fails_closed_before_repository(tmp_path, query):
    system = await create_system(
        make_test_settings(tmp_path),
        clock=MutableClock(NOW),
    )
    await system.start()

    async def forbidden_list(*_args, **_kwargs):
        raise AssertionError("unknown status expanded to repository.list")

    system.work_log_service._repository.list = forbidden_list
    try:
        with pytest.raises(FailureException) as failure:
            await system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input=query,
                    workspace_key=WorkspaceKey(trace_id="status-trace"),
                )
            )
        assert failure.value.failure.code == "work_log.query_invalid"
        assert failure.value.failure.trace_id == "status-trace"
    finally:
        await system.shutdown()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("查看状态为completed的工作记录", WorkLogStatus.COMPLETED),
        ("查看状态为已完成的工作记录", WorkLogStatus.COMPLETED),
        ("查看状态为进行中的工作记录", WorkLogStatus.IN_PROGRESS),
        ("查看状态为阻塞的工作记录", WorkLogStatus.BLOCKED),
        ("查看状态为信息的工作记录", WorkLogStatus.INFORMATIONAL),
    ],
)
def test_supported_status_maps_deterministically(text, expected):
    identifier, values = parse_work_log_query(
        text, now=NOW, timezone_name="Asia/Shanghai"
    )
    assert identifier is None
    assert values["status"] == expected


@pytest.mark.parametrize(
    "candidate",
    [
        "wl_",
        "wl_1",
        "wl_123",
        "wl_" + "z" * 32,
        "wl_ABCDEFABCDEFABCDEFABCDEFABCDEFAB",
        "wl_0123456789abcdef0123456789abcde",
        "wl_0123456789abcdef0123456789abcdef0",
        "wl_0123456789abcdef0123456789abcdeg",
        "wl_legacy_",
        "wl_legacy_bad",
        "wl_legacy_123",
        "wl_legacy_" + "a" * 63,
        "wl_legacy_" + "a" * 65,
        "wl_legacy_" + "a" * 63 + "z",
        "wl_legacy_" + "A" * 64,
        "inbox_wl_",
        "inbox_wl_bad",
        "inbox_wl_" + "a" * 23,
        "inbox_wl_" + "a" * 25,
        "inbox_wl_" + "a" * 23 + "z",
        "inbox_wl_" + "A" * 24,
        "WL_",
        "WL_bad",
        "WL_" + "z" * 32,
        "WL_0123456789abcdef0123456789abcdef",
        "WL_LEGACY_",
        "WL_LEGACY_bad",
        "INBOX_WL_",
        "INBOX_WL_bad",
        "Wl_",
        "wL_",
        "Wl_bad",
        "wL_" + "z" * 32,
        "Wl_Legacy_bad",
        "WL_legacy_bad",
        "wl_LEGACY_bad",
        "Inbox_Wl_bad",
        "INBOX_wl_bad",
        "inbox_WL_bad",
    ],
)
def test_explicit_work_log_id_candidates_are_preserved_for_service_validation(
    candidate,
):
    identifier, values = parse_work_log_query(
        f"查看工作记录 {candidate}",
        now=NOW,
        timezone_name="Asia/Shanghai",
    )
    assert identifier == candidate
    assert values == {}


@pytest.mark.parametrize(
    ("text", "candidate"),
    [
        ("查看工作记录：wl_bad", "wl_bad"),
        ("查看工作记录 wl_bad。", "wl_bad"),
        ("查询工作日志 wl_bad？", "wl_bad"),
        ("帮我看看 wl_bad", "wl_bad"),
        ("查看这个工作记录 wl_bad，谢谢", "wl_bad"),
        ("查看工作记录 WL_bad。", "WL_bad"),
        ("查询工作日志 WL_bad？", "WL_bad"),
        ("查看这个工作记录 INBOX_WL_bad，谢谢", "INBOX_WL_bad"),
    ],
)
def test_work_log_id_candidate_token_stops_before_punctuation(text, candidate):
    identifier, values = parse_work_log_query(
        text,
        now=NOW,
        timezone_name="Asia/Shanghai",
    )
    assert identifier == candidate
    assert values == {}


@pytest.mark.parametrize(
    "candidate",
    [
        "wl_" + "a" * 32,
        "wl_legacy_" + "b" * 64,
        "inbox_wl_" + "c" * 24,
    ],
)
def test_valid_work_log_ids_are_returned_unchanged(candidate):
    identifier, values = parse_work_log_query(
        f"查看工作记录 {candidate}",
        now=NOW,
        timezone_name="Asia/Shanghai",
    )
    assert identifier == candidate
    assert values == {}


@pytest.mark.parametrize(
    "query",
    [
        "查看今天的工作记录",
        "查看工作记录",
        "查看张经理相关的工作记录",
        "查看标签为蜂蜡的工作记录",
        "查看状态为已完成的工作记录",
        "查看 2026-07-20 到 2026-07-23 的工作记录",
    ],
)
def test_queries_without_work_log_id_candidates_remain_list_queries(query):
    identifier, _values = parse_work_log_query(
        query,
        now=NOW,
        timezone_name="Asia/Shanghai",
    )
    assert identifier is None


@pytest.mark.parametrize(
    "other_identifier",
    [
        "ut_task",
        "rem_reminder",
        "wf_follow_up",
        "inbox_capture",
        "UT_task",
        "REM_reminder",
        "WF_followup",
        "INBOX_item",
        "task-001",
        "raw-memory-id",
    ],
)
def test_other_identifier_prefixes_are_not_work_log_candidates(other_identifier):
    identifier, _values = parse_work_log_query(
        f"查看工作记录 {other_identifier}",
        now=NOW,
        timezone_name="Asia/Shanghai",
    )
    assert identifier is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate",
    [
        "WL_" + "z" * 32,
        "WL_bad",
        "WL_" + "a" * 32,
        "WL_LEGACY_bad",
        "INBOX_WL_bad",
        "Wl_bad",
    ],
)
async def test_explicit_invalid_id_fails_closed_without_query_or_side_effects(
    tmp_path, monkeypatch, candidate
):
    system = await create_system(
        make_test_settings(tmp_path),
        clock=MutableClock(NOW),
    )
    await system.start()
    workspace = WorkspaceKey(
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        namespace="ops",
        trace_id="acc-018-invalid-id",
    )
    try:
        for index in range(4):
            await system.work_log_service.create_from_input(
                workspace_key=workspace,
                subject=f"existing {index}",
                raw_text=f"existing {index}",
                source="api",
                context_refs=[],
            )
        with system.database_manager.lease("episodic") as conn:
            before = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )

        calls = {"get": 0, "query": 0, "repository_list": 0, "events": 0, "llm": 0}
        original_get = system.work_log_service.get

        async def observed_get(*args, **kwargs):
            calls["get"] += 1
            assert kwargs["work_log_id"] == candidate
            return await original_get(*args, **kwargs)

        async def forbidden_query(*_args, **_kwargs):
            calls["query"] += 1
            raise AssertionError("invalid explicit ID fell back to query_from_input")

        async def forbidden_list(*_args, **_kwargs):
            calls["repository_list"] += 1
            raise AssertionError("invalid explicit ID fell back to repository.list")

        async def count_event(_event):
            calls["events"] += 1

        async def forbidden_llm(*_args, **_kwargs):
            calls["llm"] += 1
            raise AssertionError("explicit Work Log ID query invoked the LLM")

        monkeypatch.setattr(system.work_log_service, "get", observed_get)
        monkeypatch.setattr(
            system.work_log_service, "query_from_input", forbidden_query
        )
        monkeypatch.setattr(
            system.work_log_service._repository, "list", forbidden_list
        )
        monkeypatch.setattr(system.llm_provider, "generate", forbidden_llm)
        system.event_bus.add_after_publish_hook(count_event)

        with pytest.raises(FailureException) as failure:
            await system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input=f"查看工作记录 {candidate}",
                    workspace_key=workspace,
                )
            )
        info = failure.value.failure
        assert info.code == "work_log.id_invalid"
        assert info.category == ErrorCategory.VALIDATION
        assert info.operation == "get"
        assert info.trace_id == "acc-018-invalid-id"
        assert calls == {
            "get": 1,
            "query": 0,
            "repository_list": 0,
            "events": 0,
            "llm": 0,
        }

        with system.database_manager.lease("episodic") as conn:
            after = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )
        assert json.dumps(before, ensure_ascii=False, default=str) == json.dumps(
            after, ensure_ascii=False, default=str
        )
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_not_configured_uses_stable_work_log_failure():
    app = CEOAssistant(
        work_log_service=None,
        clock=MutableClock(NOW),
        timezone_name="Asia/Shanghai",
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    request = ApplicationRequest(
        application_name="ceo-assistant",
        user_input="查看今天的工作记录",
        workspace_key=WorkspaceKey(trace_id="not-configured-trace"),
    )
    with pytest.raises(FailureException) as failure:
        await app.run(request)
    info = failure.value.failure
    assert info.code == "work_log.not_configured"
    assert info.category == ErrorCategory.NOT_CONFIGURED
    assert info.trace_id == "not-configured-trace"
    assert info.message == "工作记录服务尚未配置。"


def test_work_log_presenter_changes_only_message():
    original = FailureInfo(
        code="work_log.repository_failed",
        category=ErrorCategory.PERSISTENCE_FAILURE,
        message="Work Log repository operation failed",
        component="work_log",
        operation="list",
        retryable=True,
        trace_id="presenter-trace",
        cause_type="WorkLogRepositoryError",
        details={"safe": "value"},
    )
    presented = WorkLogUserErrorPresenter.present(original)
    before = original.model_dump()
    after = presented.model_dump()
    assert before.pop("message") != after.pop("message")
    assert before == after


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository_error", "expected_code", "expected_retryable"),
    [
        (
            WorkLogRepositoryError("unavailable"),
            "work_log.repository_failed",
            True,
        ),
        (
            WorkLogLegacyProjectionError(
                "malformed", row_digest="digest", field="subject"
            ),
            "work_log.legacy_projection_failed",
            False,
        ),
    ],
)
async def test_repository_failures_preserve_machine_fields(
    tmp_path, repository_error, expected_code, expected_retryable
):
    system = await create_system(
        make_test_settings(tmp_path),
        clock=MutableClock(NOW),
    )
    await system.start()

    async def failing_list(*_args, **_kwargs):
        raise repository_error

    system.work_log_service._repository.list = failing_list
    try:
        with pytest.raises(FailureException) as failure:
            await system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input="查看今天的工作记录",
                    workspace_key=WorkspaceKey(trace_id="repository-trace"),
                )
            )
        info = failure.value.failure
        assert info.code == expected_code
        assert info.component == "work_log"
        assert info.operation == "list"
        assert info.retryable is expected_retryable
        assert info.trace_id == "repository-trace"
        if expected_code == "work_log.legacy_projection_failed":
            assert info.details == {"row_digest": "digest", "field": "subject"}
    finally:
        await system.shutdown()


@pytest.mark.parametrize(
    ("now", "expected_hours", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
            23,
            "2026-03-08T05:00:00+00:00",
            "2026-03-09T04:00:00+00:00",
        ),
        (
            datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
            25,
            "2026-11-01T04:00:00+00:00",
            "2026-11-02T05:00:00+00:00",
        ),
    ],
)
def test_today_dst_range_uses_local_calendar_boundaries(
    now, expected_hours, expected_start, expected_end
):
    _identifier, values = parse_work_log_query(
        "查看今天的工作记录",
        now=now,
        timezone_name="America/New_York",
    )
    assert values["date_from"].isoformat() == expected_start
    assert values["date_to"].isoformat() == expected_end
    duration = values["date_to"] - values["date_from"]
    assert duration.total_seconds() == expected_hours * 3600


@pytest.mark.parametrize(
    ("local_date", "expected_hours"),
    [("2026-03-08", 23), ("2026-11-01", 25)],
)
def test_explicit_dst_date_range_uses_next_local_midnight(
    local_date, expected_hours
):
    _identifier, values = parse_work_log_query(
        f"查看 {local_date} 到 {local_date} 的工作记录",
        now=NOW,
        timezone_name="America/New_York",
    )
    duration = values["date_to"] - values["date_from"]
    assert duration.total_seconds() == expected_hours * 3600
