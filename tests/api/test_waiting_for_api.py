import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_system
from api.routes.waiting_for import router
from core.database import DatabaseManager
from core.waiting_for import SQLiteWaitingForRepository, WaitingForService


class Clock:
    def now(self):
        return datetime(2026, 7, 22, 8, tzinfo=timezone.utc)


def test_waiting_for_api_contract_and_lifecycle(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    clock = Clock()
    service = WaitingForService(repository, bus=None, clock=clock)
    asyncio.run(service.initialize())
    system = SimpleNamespace(waiting_for_service=service, clock=clock)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_system] = lambda: system

    with TestClient(app) as client:
        created = client.post(
            "/waiting-for",
            json={
                "subject": "供应商回复",
                "waiting_on": "包装供应商",
                "next_review_at": (clock.now() + timedelta(days=1)).isoformat(),
                "timezone": "Asia/Shanghai",
            },
        )
        assert created.status_code == 201
        created_payload = created.json()
        item = created_payload["item"]
        assert created_payload["event"]["event_type"] == "created"
        item_id = item["id"]
        assert item["status"] == "open" and item["revision"] == 1
        assert client.get("/waiting-for").json()["items"][0]["id"] == item_id
        assert client.get(f"/waiting-for/{item_id}").status_code == 200

        follow_up = client.post(
            f"/waiting-for/{item_id}/follow-ups",
            json={"expected_revision": 1, "note": "已邮件催办"},
        ).json()["item"]
        snoozed = client.post(
            f"/waiting-for/{item_id}/snooze",
            json={
                "expected_revision": follow_up["revision"],
                "next_review_at": (clock.now() + timedelta(days=2)).isoformat(),
            },
        ).json()["item"]
        resolved = client.post(
            f"/waiting-for/{item_id}/resolve",
            json={
                "expected_revision": snoozed["revision"],
                "resolution_note": "已经确认",
            },
        ).json()["item"]
        reopened = client.post(
            f"/waiting-for/{item_id}/reopen",
            json={"expected_revision": resolved["revision"], "note": "需要再次确认"},
        ).json()["item"]
        cancelled = client.post(
            f"/waiting-for/{item_id}/cancel",
            json={"expected_revision": reopened["revision"], "note": "不再需要"},
        ).json()["item"]
        assert cancelled["status"] == "cancelled"
        history = client.get(f"/waiting-for/{item_id}/events").json()
        assert [event["event_type"] for event in history["items"]] == [
            "created", "followed_up", "snoozed", "resolved", "reopened", "cancelled"
        ]

    manager.close_all()
