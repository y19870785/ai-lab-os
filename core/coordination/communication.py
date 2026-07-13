"""Agent Message Bus —— Agent 间通信基础设施。

基于 Event Bus 实现，支持：
- 点对点消息（send）
- 广播消息（broadcast）
- 请求-响应（request）
- 消息历史查询

所有消息通过底层 Event Bus 发布 coordination.message.* 事件。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from core.coordination.models import (
    AgentMessage, AgentMessageResponse, MessagePriority,
)
from core.coordination.protocol import MessageBusProtocol
from core.coordination.events import publish_coordination_event, CoordinationEventTypes
from core.coordination.exceptions import MessageDeliveryError, CoordinationTimeoutError


class AgentMessageBus(MessageBusProtocol):
    """Agent 间消息总线。

    内部使用 Event Bus + 内存队列。
    """

    def __init__(self, bus=None, config=None):
        from core.coordination.config import CoordinationConfig
        self._bus = bus
        self._config = config or CoordinationConfig()
        self._message_history: list[AgentMessage] = []
        self._agent_queues: dict[str, list[AgentMessage]] = defaultdict(list)
        self._pending_responses: dict[str, asyncio.Future] = {}

    async def initialize(self) -> None:
        self._message_history.clear()
        self._agent_queues.clear()
        self._pending_responses.clear()

    async def shutdown(self) -> None:
        for future in self._pending_responses.values():
            if not future.done():
                future.set_exception(CoordinationTimeoutError("shutdown", 0))
        self._pending_responses.clear()

    async def send(self, message: AgentMessage) -> str:
        """发送点对点消息。"""
        self._message_history.append(message)
        receiver = message.receiver

        # 放入接收者队列
        if receiver:
            self._agent_queues[receiver].append(message)

        # 通过 Event Bus 发布事件
        await publish_coordination_event(
            self._bus,
            CoordinationEventTypes.MESSAGE_SENT,
            source="coordination.message_bus",
            payload={
                "message_id": message.message_id,
                "sender": message.sender,
                "receiver": receiver,
                "message_type": message.message_type,
            },
        )
        return message.message_id

    async def broadcast(self, message: AgentMessage) -> list[str]:
        """广播消息到所有已知 Agent。"""
        sent_ids = []
        # 广播到所有已有队列的 agent
        receivers = list(self._agent_queues.keys())
        if not receivers:
            # 如果没有已知 agent，广播到 Team 的所有 agent
            # （由 Orchestrator 负责注入）
            return sent_ids

        for receiver in receivers:
            if receiver == message.sender:
                continue
            msg = AgentMessage(
                sender=message.sender,
                receiver=receiver,
                conversation_id=message.conversation_id,
                message_type=message.message_type,
                payload=message.payload,
                priority=message.priority,
            )
            await self.send(msg)
            sent_ids.append(msg.message_id)
        return sent_ids

    async def request(self, message: AgentMessage, timeout: float = 30.0) -> AgentMessageResponse:
        """发送请求并等待响应。"""
        await self.send(message)

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[message.message_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_responses.pop(message.message_id, None)
            raise CoordinationTimeoutError("request", timeout)

    async def respond(self, original_message_id: str, response: AgentMessageResponse) -> None:
        """响应一个请求。"""
        future = self._pending_responses.pop(original_message_id, None)
        if future and not future.done():
            future.set_result(response)
        else:
            # 发送响应消息
            msg = AgentMessage(
                sender=response.responder,
                receiver="",  # 回 send 的 sender
                message_type="response",
                payload={"response": response.payload, "success": response.success},
            )
            await self.send(msg)

    async def get_messages(self, agent_id: str) -> list[AgentMessage]:
        """获取指定 Agent 的所有待处理消息（并清空队列）。"""
        messages = self._agent_queues.get(agent_id, [])
        self._agent_queues[agent_id] = []
        return messages

    def message_count(self) -> int:
        return len(self._message_history)

    @property
    def history(self) -> list[AgentMessage]:
        return list(self._message_history)
