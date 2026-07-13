"""MemoryStore 抽象接口。

定义记忆存储的统一抽象层。
具体实现（Session/Episodic/Semantic/Decision）需实现此接口。

统一接口（共 8 个方法）：
- save       : 存储单条记忆
- batch_save : 批量存储
- get        : 按 ID 读取
- query      : 按条件检索
- delete     : 按 ID 删除
- count      : 统计数量
- initialize : 初始化存储（建表等）
- close      : 释放资源（关闭连接等）
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery


class MemoryStore(ABC):
    """记忆存储的统一抽象接口。

    所有 Memory Store 必须实现此接口，不允许出现某类 Store 多/少方法。
    """

    @abstractmethod
    async def save(self, item: MemoryItem) -> str:
        """存储一条记忆。返回记忆 ID。"""
        ...

    @abstractmethod
    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        """批量存储记忆。返回 ID 列表。"""
        ...

    @abstractmethod
    async def get(self, id: str) -> MemoryItem | None:
        """根据 ID 获取记忆。不存在返回 None。"""
        ...

    @abstractmethod
    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        """按条件检索记忆。返回匹配列表。"""
        ...

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """删除记忆。返回 True 表示成功删除。"""
        ...

    @abstractmethod
    async def count(self, filter: MemoryFilter | None = None) -> int:
        """统计记忆数量。filter 为 None 时返回总数。"""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """初始化存储。调用后 Store 进入可用状态。

        幂等：多次调用不会产生副作用。
        SQLite Store：建表 + 索引。
        SessionMemory：无操作。
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """释放存储资源。调用后 Store 不可再使用。

        幂等：多次调用不会抛异常。
        SQLite Store：通过 DatabaseManager 关闭连接。
        SessionMemory：清空字典。
        """
        ...