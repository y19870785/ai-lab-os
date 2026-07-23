"""Typed Work Log API, compatibility, isolation, and zero-write tests."""

import json

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
