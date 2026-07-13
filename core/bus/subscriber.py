"""订阅者实现。在内存中注册事件处理器。"""

from __future__ import annotations

from typing import Any

from core.bus.event import Event
from core.bus.protocol import EventHandler, Subscriber, Subscription
from core.bus.publisher import MemoryPublisher


class MemorySubscriber(Subscriber):
    """内存订阅者。通过 MemoryPublisher 注册事件处理器。"""

    def __init__(self, publisher: MemoryPublisher) -> None:
        self._publisher = publisher

    async def subscribe(self, topic: str, handler: EventHandler) -> Subscription:
        """订阅指定 topic。"""
        sub = Subscription(topic)
        self._publisher.add_subscriber(topic, handler, sub)
        return sub

    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """取消订阅。"""
        self._publisher.remove_subscriber(topic, handler)
