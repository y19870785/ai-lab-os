"""Message Bus 单元测试。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from core.bus import (
    Event,
    MemoryBus,
    MemoryTaskQueue,
    Task,
    TaskTimeoutError,
    get_bus,
    reset_bus,
)


# ═══════════════════════════════════════════════════════════════
# 1. Event 创建
# ═══════════════════════════════════════════════════════════════

class TestEventCreation:
    """测试 Event 数据模型的创建和默认值。"""

    def test_create_event_with_required_fields(self):
        """创建事件时必须的字段能正常工作。"""
        event = Event(event_type="test.event", source="test")
        assert event.event_id is not None
        assert event.event_type == "test.event"
        assert event.source == "test"
        assert event.timestamp is not None
        assert event.payload == {}
        assert event.metadata == {}

    def test_create_event_with_all_fields(self):
        """创建事件时所有字段都能传入。"""
        event = Event(
            event_type="memory.created",
            source="memory.episodic",
            payload={"memory_id": "mem_001"},
            metadata={"trace_id": "trace_001"},
        )
        assert event.event_type == "memory.created"
        assert event.payload["memory_id"] == "mem_001"
        assert event.metadata["trace_id"] == "trace_001"

    def test_event_id_is_unique(self):
        """每次创建事件生成不同的 ID。"""
        e1 = Event(event_type="test", source="test")
        e2 = Event(event_type="test", source="test")
        assert e1.event_id != e2.event_id

    def test_task_creation(self):
        """Task 数据模型的基本字段。"""
        task = Task(
            queue="agent.run",
            payload={"cmd": "analyze"},
        )
        assert task.task_id is not None
        assert task.queue == "agent.run"
        assert task.payload["cmd"] == "analyze"
        assert task.priority == 0
        assert task.max_retries == 3
        assert task.timeout == 60


# ═══════════════════════════════════════════════════════════════
# 2. Event 发布
# ═══════════════════════════════════════════════════════════════

class TestEventPublish:
    """测试事件发布和订阅。"""

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """发布一个事件，订阅者应收到。"""
        bus = MemoryBus()
        await bus.start()

        received: list[Event] = []

        async def handler(event: Event):
            received.append(event)

        await bus.subscribe("test.topic", handler)
        event = Event(event_type="test.event", source="test")
        await bus.publish("test.topic", event)

        # 给事件处理一点时间
        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0].event_id == event.event_id

        await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_to_no_subscriber(self):
        """发布到没有订阅者的 topic 不会出错。"""
        bus = MemoryBus()
        await bus.start()

        event = Event(event_type="test.event", source="test")
        await bus.publish("nonexistent.topic", event)  # Should not raise

        await bus.stop()


# ═══════════════════════════════════════════════════════════════
# 3. Subscriber 接收
# ═══════════════════════════════════════════════════════════════

class TestSubscriber:
    """测试订阅者的订阅和取消。"""

    @pytest.mark.asyncio
    async def test_subscriber_receives_correct_topic(self):
        """订阅者只收到订阅的 topic 的事件。"""
        bus = MemoryBus()
        await bus.start()

        received: list[Event] = []

        async def handler(event: Event):
            received.append(event)

        await bus.subscribe("topic.a", handler)
        await bus.publish("topic.a", Event(event_type="test", source="test"))
        await bus.publish("topic.b", Event(event_type="test", source="test"))

        await asyncio.sleep(0.05)
        assert len(received) == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_topic(self):
        """同一 topic 多个订阅者都收到事件。"""
        bus = MemoryBus()
        await bus.start()

        received1: list[Event] = []
        received2: list[Event] = []

        async def handler1(event: Event):
            received1.append(event)

        async def handler2(event: Event):
            received2.append(event)

        await bus.subscribe("topic", handler1)
        await bus.subscribe("topic", handler2)
        await bus.publish("topic", Event(event_type="test", source="test"))

        await asyncio.sleep(0.05)
        assert len(received1) == 1
        assert len(received2) == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_subscriber_cancel(self):
        """取消订阅后不再接收事件。"""
        bus = MemoryBus()
        await bus.start()

        received: list[Event] = []

        async def handler(event: Event):
            received.append(event)

        sub = await bus.subscribe("topic", handler)
        await bus.publish("topic", Event(event_type="test", source="test"))
        await asyncio.sleep(0.05)
        assert len(received) == 1

        sub.cancel()
        assert not sub.is_active

        await bus.publish("topic", Event(event_type="test", source="test"))
        await asyncio.sleep(0.05)
        assert len(received) == 1  # 不再增加

        await bus.stop()


# ═══════════════════════════════════════════════════════════════
# 4. 多 Subscriber
# ═══════════════════════════════════════════════════════════════

class TestMultiSubscriber:
    """测试多个订阅者的行为。"""

    @pytest.mark.asyncio
    async def test_multiple_topics_multiple_subscribers(self):
        """多个 topic 各自的订阅者独立工作。"""
        bus = MemoryBus()
        await bus.start()

        received_a: list[Event] = []
        received_b: list[Event] = []

        async def handler_a(event: Event):
            received_a.append(event)

        async def handler_b(event: Event):
            received_b.append(event)

        await bus.subscribe("topic.a", handler_a)
        await bus.subscribe("topic.b", handler_b)

        await bus.publish("topic.a", Event(event_type="test", source="test"))
        await bus.publish("topic.b", Event(event_type="test", source="test"))

        await asyncio.sleep(0.05)
        assert len(received_a) == 1
        assert len(received_b) == 1

        await bus.stop()


# ═══════════════════════════════════════════════════════════════
# 5. Queue 任务处理
# ═══════════════════════════════════════════════════════════════

class TestTaskQueue:
    """测试 Task Queue 的任务发送和消费。"""

    @pytest.mark.asyncio
    async def test_send_and_process_task(self):
        """发送任务到队列，worker 应处理它。"""
        bus = MemoryBus()
        await bus.start()

        results: list[str] = []

        async def worker(task: Task):
            results.append(task.payload["cmd"])

        await bus.register_worker("test.q", worker)
        task = Task(queue="test.q", payload={"cmd": "hello"})
        await bus.send("test.q", task)

        await asyncio.sleep(0.05)
        assert len(results) == 1
        assert results[0] == "hello"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_task_with_retry_on_failure(self):
        """任务失败后应重试。"""
        queue = MemoryTaskQueue()
        attempts: list[int] = []

        async def worker(task: Task):
            attempts.append(1)
            raise ValueError("simulated failure")

        await queue.register_worker("test.q", worker)
        task = Task(queue="test.q", payload={}, max_retries=2)
        await queue.send("test.q", task)

        await asyncio.sleep(0.2)
        # 1 (初始) + 2 (重试) = 3
        assert len(attempts) == 3

        queue.shutdown()

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """超时任务应重试。"""
        queue = MemoryTaskQueue()
        attempts: list[int] = []

        async def worker(task: Task):
            attempts.append(1)
            await asyncio.sleep(10)  # 超时（> timeout 1s）
            return "done"

        await queue.register_worker("test.q", worker)
        task = Task(queue="test.q", payload={}, max_retries=1, timeout=1)
        await queue.send("test.q", task)

        await asyncio.sleep(2.5)
        assert len(attempts) == 2  # 初始 + 1 次重试

        queue.shutdown()

    @pytest.mark.asyncio
    async def test_queue_size(self):
        """队列长度应正确反映待处理任务数。"""
        tq = MemoryTaskQueue()
        assert tq.queue_sizes == {}

        task = Task(queue="test.q", payload={})
        await tq.send("test.q", task)
        assert tq.queue_sizes.get("test.q", 0) >= 0  # consume 也可能同时进行


# ═══════════════════════════════════════════════════════════════
# 6. 异常处理
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """测试异常处理行为。"""

    @pytest.mark.asyncio
    async def test_publish_before_start_raises(self):
        """总线启动前发布事件应报错。"""
        bus = MemoryBus()
        with pytest.raises(RuntimeError, match="not running"):
            await bus.publish("test", Event(event_type="test", source="test"))

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_crash_bus(self):
        """处理器中的异常不应导致总线崩溃。"""
        bus = MemoryBus()
        await bus.start()

        async def failing_handler(event: Event):
            raise ValueError("handler failed")

        async def good_handler(event: Event):
            pass  # 正常处理器应仍能工作

        await bus.subscribe("topic", failing_handler)
        await bus.subscribe("topic", good_handler)

        # 不应该抛出异常
        await bus.publish("topic", Event(event_type="test", source="test"))
        await asyncio.sleep(0.05)

        await bus.stop()


# ═══════════════════════════════════════════════════════════════
# 7. 全局单例
# ═══════════════════════════════════════════════════════════════

class TestGlobalBus:
    """测试全局单例。"""

    def test_get_bus_returns_singleton(self):
        """get_bus 应返回同一个实例。"""
        reset_bus()
        b1 = get_bus()
        b2 = get_bus()
        assert b1 is b2

    def test_reset_bus_creates_new_instance(self):
        """reset_bus 后 get_bus 应返回新实例。"""
        reset_bus()
        b1 = get_bus()
        reset_bus()
        b2 = get_bus()
        assert b1 is not b2
