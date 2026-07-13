"""发布者实现。在内存中维护订阅者列表并分发事件。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from core.bus.event import Event
from core.bus.protocol import EventHandler, Publisher, Subscription


class MemoryPublisher(Publisher):
    """内存发布者。维护 topic → handlers 映射，发布时并发分发。"""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[tuple[EventHandler, Subscription]]] = (
            defaultdict(list)
        )

    async def publish(self, topic: str, event: Event) -> None:
        """发布事件，并发通知所有活跃订阅者。"""
        subs = self._subscribers.get(topic, [])
        tasks = []
        for handler, sub in subs:
            if sub.is_active:
                tasks.append(asyncio.ensure_future(handler(event)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def add_subscriber(self, topic: str, handler: EventHandler, sub: Subscription) -> None:
        """添加订阅（由 Subscriber 调用）。"""
        self._subscribers[topic].append((handler, sub))

    def remove_subscriber(self, topic: str, handler: EventHandler) -> bool:
        """移除订阅。返回 True 如果找到并移除。"""
        subs = self._subscribers.get(topic, [])
        before = len(subs)
        self._subscribers[topic] = [(h, s) for h, s in subs if h is not handler]
        return len(self._subscribers[topic]) < before

    @property
    def subscriber_count(self) -> int:
        """当前注册的订阅者总数。"""
        return sum(len(v) for v in self._subscribers.values())
