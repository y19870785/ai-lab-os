"""任务队列实现。基于 asyncio.Queue 的内存任务队列。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from core.bus.event import Task
from core.bus.protocol import TaskQueue, TaskWorker


class TaskTimeoutError(TimeoutError):
    """任务执行超时。"""
    pass


class MemoryTaskQueue(TaskQueue):
    """内存任务队列。

    使用 asyncio.Queue 实现。Phase 1 基础版本，后续可扩展为：
    - 优先级队列
    - 延迟队列
    - 分布式队列（Redis/RabbitMQ）
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Task]] = defaultdict(
            lambda: asyncio.Queue()
        )
        self._workers: dict[str, list[TaskWorker]] = defaultdict(list)
        self._running = True

    async def send(self, queue: str, task: Task) -> str:
        """发送任务到指定队列。"""
        await self._queues[queue].put(task)
        return task.task_id

    async def register_worker(self, queue: str, worker: TaskWorker) -> None:
        """注册 worker 并开始消费。"""
        self._workers[queue].append(worker)
        asyncio.ensure_future(self._consume(queue, worker))

    async def _consume(self, queue: str, worker: TaskWorker) -> None:
        """消费队列中的任务。处理异常、超时和重试。"""
        q = self._queues[queue]
        while self._running:
            task = await q.get()
            retries = 0
            while retries <= task.max_retries:
                try:
                    await asyncio.wait_for(
                        worker(task),
                        timeout=task.timeout,
                    )
                    break  # 成功
                except asyncio.TimeoutError:
                    retries += 1
                    if retries > task.max_retries:
                        # TODO: 发布 task.failed 事件
                        pass
                except Exception:
                    retries += 1
                    if retries > task.max_retries:
                        # TODO: 发布 task.failed 事件
                        pass
            q.task_done()

    @property
    def queue_sizes(self) -> dict[str, int]:
        """各队列的当前长度。"""
        return {k: v.qsize() for k, v in self._queues.items()}

    def shutdown(self) -> None:
        """关闭队列系统。"""
        self._running = False
