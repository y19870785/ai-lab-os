"""消息总线组合实现。

将 Publisher、Subscriber、TaskQueue 组合为一个完整的 MessageBus。
集成 Logging 系统进行事件审计。
预留 Memory 事件接口。

使用方式：
    from core.bus import get_bus

    bus = get_bus()
    await bus.start()

    # 发布事件
    event = Event(event_type="memory.created", source="test", payload={})
    await bus.publish("memory.created", event)

    # 订阅事件
    await bus.subscribe("memory.created", handler)

    # 发送任务
    task = Task(queue="agent.run", payload={"cmd": "analyze"})
    await bus.send("agent.run", task)

    await bus.stop()
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.bus.event import Event, Task
from core.bus.protocol import (
    EventHandler,
    MessageBus,
    Subscription,
    TaskWorker,
)
from core.bus.publisher import MemoryPublisher
from core.bus.subscriber import MemorySubscriber
from core.bus.queue import MemoryTaskQueue
from core.logging import get_logger

logger = get_logger("core.bus")


class MemoryBus(MessageBus):
    """完整的内存消息总线实现。

    组合 MemoryPublisher、MemorySubscriber、MemoryTaskQueue。
    加入日志审计和事件过滤能力。
    """

    def __init__(self) -> None:
        self._publisher = MemoryPublisher()
        self._subscriber = MemorySubscriber(self._publisher)
        self._task_queue = MemoryTaskQueue()
        self._running = False

        # 内部事件钩子
        self._before_publish: list[EventHandler] = []
        self._after_publish: list[EventHandler] = []

    # ── 生命周期 ──

    async def start(self) -> None:
        """启动总线。"""
        self._running = True
        logger.info("bus.started", extra={"subscriber_count": self._publisher.subscriber_count})

    async def stop(self) -> None:
        """停止总线。"""
        self._running = False
        self._task_queue.shutdown()
        logger.info("bus.stopped")

    async def wait_closed(self) -> None:
        """等待所有任务处理完成。"""
        if self._running:
            await self.stop()

    # ── Event Bus ──

    async def publish(self, topic: str, event: Event) -> None:
        """发布事件。自动注入审计元数据并触发钩子。"""
        if not self._running:
            raise RuntimeError("Bus is not running")

        # 前置钩子
        for hook in self._before_publish:
            await hook(event)

        await self._publisher.publish(topic, event)

        # 后置钩子 + 日志
        for hook in self._after_publish:
            await hook(event)
        logger.debug(
            "event.published",
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "topic": topic,
                "source": event.source,
            },
        )

    async def subscribe(self, topic: str, handler: EventHandler) -> Subscription:
        """订阅事件。"""
        sub = await self._subscriber.subscribe(topic, handler)
        logger.debug("event.subscribed", extra={"topic": topic})
        return sub

    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """取消订阅。"""
        await self._subscriber.unsubscribe(topic, handler)

    # ── Task Queue ──

    async def send(self, queue: str, task: Task) -> str:
        """发送任务。"""
        task_id = await self._task_queue.send(queue, task)
        logger.debug(
            "task.sent",
            extra={
                "task_id": task_id,
                "queue": queue,
                "priority": task.priority,
            },
        )
        return task_id

    async def register_worker(self, queue: str, worker: TaskWorker) -> None:
        """注册 worker。"""
        await self._task_queue.register_worker(queue, worker)

    # ── 钩子管理 ──

    def add_before_publish_hook(self, hook: EventHandler) -> None:
        """添加发布前钩子。"""
        self._before_publish.append(hook)

    def add_after_publish_hook(self, hook: EventHandler) -> None:
        """添加发布后钩子。"""
        self._after_publish.append(hook)

    # ── 状态 ──

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscriber_count(self) -> int:
        return self._publisher.subscriber_count


# ── 全局单例 ──

_bus: MemoryBus | None = None


def get_bus() -> MemoryBus:
    """获取全局 Message Bus 单例。"""
    global _bus
    if _bus is None:
        _bus = MemoryBus()
    return _bus


def reset_bus() -> None:
    """重置总线（测试用）。"""
    global _bus
    _bus = None
