"""Typed Work Log API, compatibility, isolation, and zero-write tests."""

import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings


def test_typed_create_list_get_headers_filters_and_compatibility(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    alpha = {
        "X-Tenant-ID": "tenant",
        "X-Workspace-ID": "alpha",
        "X-Namespace": "ops",
    }
    beta = {**alpha, "X-Workspace-ID": "beta"}
    with TestClient(app) as client:
        created = client.post(
            "/work-logs",
            headers=alpha,
            json={
                "subject": "完成蜂蜡验货",
                "raw_text": "张经理确认完成蜂蜡验货",
                "target": "张经理",
                "status": "completed",
                "tags": ["蜂蜡"],
                "context_refs": [
                    {"kind": "inbox", "target_id": "inbox_source"}
                ],
            },
        )
        assert created.status_code == 200
        record = created.json()
        assert record["id"].startswith("wl_")
        assert record["source"] == "api"

        listing = client.get(
            "/work-logs",
            headers=alpha,
            params={
                "target": "张经理",
                "tags": "蜂蜡",
                "status": "completed",
                "text": "验货",
                "context_ref": "inbox_source",
                "limit": 1,
            },
        )
        assert listing.status_code == 200
        assert listing.json()["items"][0]["id"] == record["id"]
        assert listing.json()["total_count"] == 1
        assert client.get(
            f"/work-logs/{record['id']}", headers=alpha
        ).json()["id"] == record["id"]
        assert client.get("/work-logs", headers=beta).json()["items"] == []

        compatibility = client.post(
            "/work-logs", headers=alpha, json={"user_input": "兼容入口"}
        )
        assert compatibility.status_code == 200
        assert compatibility.json()["status"] == "ok"
        assert compatibility.json()["metadata"]["source"] == "api"


def test_legacy_get_alias_and_get_are_zero_write(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    headers = {
        "X-Tenant-ID": "default",
        "X-Workspace-ID": "default",
        "X-Namespace": "default",
    }
    with TestClient(app) as client:
        manager = app.state.system.database_manager
        with manager.lease("episodic") as conn:
            conn.execute(
                """
                INSERT INTO episodic_memories
                (id,memory_type,content,importance,timestamp,metadata)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    "legacy-api-row",
                    "episodic",
                    json.dumps(
                        {
                            "type": "work_log",
                            "date": "2026-07-23",
                            "subject": "历史 API 记录",
                        },
                        ensure_ascii=False,
                    ),
                    0.7,
                    "2026-07-23T00:00:00+00:00",
                    "{}",
                ),
            )
            conn.commit()
            before = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )
        listing = client.get("/work-logs", headers=headers)
        legacy_id = listing.json()["items"][0]["id"]
        assert legacy_id.startswith("wl_legacy_")
        assert client.get(
            f"/work-logs/{legacy_id}", headers=headers
        ).json()["id"] == legacy_id
        with manager.lease("episodic") as conn:
            after = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )
        assert after == before


@pytest.mark.parametrize(
    ("method", "path", "payload", "params", "expected_code"),
    [
        (
            "post",
            "/work-logs",
            {
                "subject": "Invalid timezone",
                "raw_text": "Invalid timezone",
                "timezone": "Mars/Olympus",
            },
            None,
            "work_log.timezone_invalid",
        ),
        (
            "post",
            "/work-logs",
            {
                "subject": "Naive",
                "raw_text": "Naive",
                "occurred_at": "2026-07-23T10:00:00",
            },
            None,
            "work_log.occurred_at_invalid",
        ),
        (
            "post",
            "/work-logs",
            {
                "subject": "Context",
                "raw_text": "Context",
                "context_refs": [
                    {
                        "kind": "inbox",
                        "target_id": "inbox_wl_" + "a" * 24,
                    }
                ],
            },
            None,
            "work_log.context_ref_invalid",
        ),
        (
            "post",
            "/work-logs",
            {"subject": " ", "raw_text": " "},
            None,
            "work_log.subject_required",
        ),
        (
            "get",
            "/work-logs",
            None,
            {
                "date_from": "2026-07-24T00:00:00Z",
                "date_to": "2026-07-23T00:00:00Z",
            },
            "work_log.query_invalid",
        ),
        (
            "get",
            "/work-logs/raw-memory-id",
            None,
            None,
            "work_log.id_invalid",
        ),
        (
            "get",
            "/work-logs",
            None,
            {"limit": "201"},
            "work_log.limit_invalid",
        ),
        (
            "get",
            "/work-logs",
            None,
            {"offset": "10001"},
            "work_log.limit_invalid",
        ),
    ],
)
def test_invalid_inputs_use_stable_work_log_failures(
    tmp_path, method, path, payload, params, expected_code
):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            json=payload,
            params=params,
        )
    assert response.status_code >= 400
    body = response.json()
    assert body["code"] == expected_code
    assert body["trace_id"]
    assert body["retryable"] is False
    assert "traceback" not in response.text.casefold()
    assert "C:\\" not in response.text


def test_not_configured_uses_work_log_failure(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        original = app.state.system.work_log_service
        app.state.system.work_log_service = None
        try:
            response = client.get("/work-logs")
        finally:
            app.state.system.work_log_service = original
    assert response.status_code == 503
    assert response.json()["code"] == "work_log.not_configured"
    assert response.json()["trace_id"]
