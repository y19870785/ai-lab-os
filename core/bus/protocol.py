"""Message Bus 抽象接口定义。

定义核心抽象：
- EventHandler / TaskWorker：处理函数类型签名
- Subscription：订阅句柄
- Publisher / Subscriber：发布/订阅抽象
- MessageBus：组合接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Protocol

from core.bus.event import Event, Task

# ── 类型别名 ──

EventHandler = Callable[[Event], Awaitable[None]]
"""事件处理函数：接收一个 Event，异步处理。"""

TaskWorker = Callable[[Task], Awaitable[Any]]
"""任务处理函数：接收一个 Task，异步处理，返回结果。"""


# ── 订阅句柄 ──

class Subscription:
    """订阅句柄。用于取消订阅和管理订阅生命周期。"""

    def __init__(self, topic: str) -> None:
        self.topic = topic
        self._active = True

    def cancel(self) -> None:
        """取消订阅。"""
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active


class CancelToken(Protocol):
    """可取消的标记接口。"""
    @property
    def is_active(self) -> bool: ...


# ── 发布者抽象 ──

class Publisher(ABC):
    """发布者抽象。负责将事件发布到总线。"""

    @abstractmethod
    async def publish(self, topic: str, event: Event) -> None:
        """发布事件到指定 topic，所有订阅者会收到通知。"""
        ...


# ── 订阅者抽象 ──

class Subscriber(ABC):
    """订阅者抽象。负责订阅 topic 并接收事件。"""

    @abstractmethod
    async def subscribe(self, topic: str, handler: EventHandler) -> Subscription:
        """订阅指定 topic 的事件。返回 Subscription 可用于取消订阅。"""
        ...

    @abstractmethod
    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """取消订阅指定 topic 的指定处理器。"""
        ...


# ── 任务队列抽象 ──

class TaskQueue(ABC):
    """任务队列抽象。负责任务的发送和消费。"""

    @abstractmethod
    async def send(self, queue: str, task: Task) -> str:
        """发送任务到指定队列。返回 task_id。"""
        ...

    @abstractmethod
    async def register_worker(self, queue: str, worker: TaskWorker) -> None:
        """注册一个 worker 处理指定队列的任务。"""
        ...


# ── 消息总线抽象（组合接口）──

class MessageBus(Publisher, Subscriber, TaskQueue):
    """消息总线抽象。

    组合了 Publisher、Subscriber 和 TaskQueue 三个能力。
    实现类只需实现这个接口。

    支持两种通信模式：
    - Event Bus：一对多发布/订阅，通过 topic 路由
    - Task Queue：一对一任务分发，通过 queue 路由
    """

    # ── 生命周期 ──

    @abstractmethod
    async def start(self) -> None:
        """启动总线。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止总线。"""
        ...

    @abstractmethod
    async def wait_closed(self) -> None:
        """等待总线完全关闭。"""
        ...
