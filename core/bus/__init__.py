"""消息总线子系统。

AI-Lab 核心通信基础设施，提供两种通信模式：
1. Event Bus (Pub-Sub)：一对多事件广播
2. Task Queue：点对点任务分发

使用方式：
    from core.bus import get_bus, Event, Task

    bus = get_bus()
    await bus.start()

    # 发布事件
    event = Event(event_type="memory.created", source="test", payload={})
    await bus.publish("memory.created", event)

    # 订阅事件
    async def on_memory_created(event: Event):
        print(f"Memory created: {event.payload}")

    await bus.subscribe("memory.created", on_memory_created)

    # 发送任务
    task = Task(queue="agent.run", payload={"cmd": "analyze"})
    await bus.send("agent.run", task)

    await bus.stop()
"""

from core.bus.bus import MemoryBus, get_bus, reset_bus
from core.bus.event import Event, Task
from core.bus.protocol import (
    EventHandler,
    MessageBus,
    Publisher,
    Subscriber,
    Subscription,
    TaskQueue,
    TaskWorker,
)
from core.bus.memory_events import MemoryEventTypes, make_memory_event
from core.bus.queue import MemoryTaskQueue, TaskTimeoutError

__all__ = [
    # 数据模型
    "MemoryEventTypes",
    "make_memory_event",
    "Event",
    "Task",
    # 抽象接口
    "MessageBus",
    "Publisher",
    "Subscriber",
    "Subscription",
    "TaskQueue",
    "EventHandler",
    "TaskWorker",
    # 实现
    "MemoryBus",
    "MemoryTaskQueue",
    # 异常
    "TaskTimeoutError",
    # 全局入口
    "get_bus",
    "reset_bus",
]
