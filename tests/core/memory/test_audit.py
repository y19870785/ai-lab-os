"""Memory Audit tests."""
from __future__ import annotations
import asyncio
import pytest
from core.bus import Event, get_bus, reset_bus
from core.memory.audit import MemoryAuditor

class TestAuditor:
    @pytest.mark.asyncio
    async def test_auditor_start_stop(self):
        bus = get_bus(); await bus.start()
        auditor = MemoryAuditor(bus=bus)
        await auditor.start()
        assert auditor.log_count == 0
        await auditor.stop()
        await bus.stop(); reset_bus()

    @pytest.mark.asyncio
    async def test_auditor_records_event(self):
        bus = get_bus(); await bus.start()
        auditor = MemoryAuditor(bus=bus)
        await auditor.start()
        evt = Event(event_type="memory.created", source="test", payload={"memory_id": "m1"})
        await bus.publish("memory.created", evt)
        await asyncio.sleep(0.05)
        assert auditor.log_count >= 1
        entries = auditor.get_log()
        assert entries[0]["operation"] == "created"
        assert entries[0]["memory_id"] == "m1"
        await auditor.stop()
        await bus.stop(); reset_bus()

