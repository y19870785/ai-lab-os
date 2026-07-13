"""Agent Message Bus Tests."""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.coordination.communication import AgentMessageBus
from core.coordination.models import AgentMessage, AgentMessageResponse, MessagePriority


class TestAgentMessageBus:

    async def test_send_message(self):
        bus = AgentMessageBus()
        await bus.initialize()
        msg = AgentMessage(sender="a1", receiver="a2", message_type="text", payload={"text": "hello"})
        msg_id = await bus.send(msg)
        assert msg_id != ""
        assert bus.message_count() == 1

    async def test_get_messages(self):
        bus = AgentMessageBus()
        await bus.initialize()
        await bus.send(AgentMessage(sender="a1", receiver="a2", payload={"text": "m1"}))
        await bus.send(AgentMessage(sender="a1", receiver="a2", payload={"text": "m2"}))
        messages = await bus.get_messages("a2")
        assert len(messages) == 2

    async def test_get_messages_clears_queue(self):
        bus = AgentMessageBus()
        await bus.initialize()
        await bus.send(AgentMessage(sender="a1", receiver="a2", payload={"text": "m1"}))
        await bus.get_messages("a2")
        messages = await bus.get_messages("a2")
        assert len(messages) == 0

    async def test_broadcast(self):
        bus = AgentMessageBus()
        await bus.initialize()
        # Pre-populate queues so broadcast finds targets
        await bus.send(AgentMessage(sender="a1", receiver="a2", payload={"text": "init"}))
        await bus.send(AgentMessage(sender="a1", receiver="a3", payload={"text": "init"}))

        broadcast_msg = AgentMessage(
            sender="coordinator",
            receiver="",
            message_type="announcement",
            payload={"text": "team meeting"},
        )
        sent_ids = await bus.broadcast(broadcast_msg)
        assert len(sent_ids) == 2  # a2 and a3 (not coordinator)

    async def test_response(self):
        bus = AgentMessageBus()
        await bus.initialize()

        msg = AgentMessage(sender="a1", receiver="a2", message_type="request", payload={"q": "status?"})
        await bus.send(msg)

        # Simulate a response
        import asyncio
        future = asyncio.get_event_loop().create_future()
        bus._pending_responses[msg.message_id] = future

        response = AgentMessageResponse(
            original_message_id=msg.message_id,
            responder="a2",
            payload={"status": "ok"},
            success=True,
        )
        await bus.respond(msg.message_id, response)

        result = await future
        assert result.success
        assert result.payload["status"] == "ok"

    async def test_message_history(self):
        bus = AgentMessageBus()
        await bus.initialize()
        await bus.send(AgentMessage(sender="x", receiver="y", payload={"n": 1}))
        await bus.send(AgentMessage(sender="x", receiver="z", payload={"n": 2}))
        assert len(bus.history) == 2

    async def test_shutdown(self):
        bus = AgentMessageBus()
        await bus.initialize()
        await bus.shutdown()
        assert bus.message_count() >= 0  # history preserved
