# ADR-004: Memory 数据模型与持久化策略

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 004                                  |
| **标题**     | Memory 数据模型与持久化策略              |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-002                              |
| **取代**     | —                                    |

## 1. 背景

Memory Layer 需要处理三种不同特性的记忆数据，它们在数据模型、持久化策略和生命周期上各不相同。需要统一的存取入口，同时允许各自采用最合适的存储策略。

## 2. 决策

### 2.1 统一入口 + 分层存储

整体策略：一个 `MemoryInterface` 提供统一 API 入口，内部按记忆类型路由到不同的 `MemoryStore` 实现。

```python
# 内部路由逻辑示意
class MemoryInterface:
    def __init__(self):
        self._stores: dict[MemoryType, MemoryStore] = {
            MemoryType.SESSION: SessionMemoryStore(),
            MemoryType.EPISODIC: EpisodicMemoryStore(),
            MemoryType.SEMANTIC: SemanticMemoryStore(),
        }

    async def store(self, item: MemoryItem) -> str:
        store = self._stores[item.memory_type]
        return await store.save(item)
```

### 2.2 各记忆类型的持久化策略

| 记忆类型   | Phase 1 存储 | 持久化方式     | 备份策略         | 生命周期         |
| ---------- | ------------ | -------------- | ---------------- | ---------------- |
| Session    | 内存 dict    | 进程内存       | 不备份（易失）    | TTL 3600s        |
| Episodic   | Chroma       | 本地文件系统    | 文件备份         | 重要性驱动过期    |
| Semantic   | SQLite       | 本地数据库文件  | SQLite Dump 备份 | 永不过期（手动清理）|

### 2.3 MemoryItem 统一数据模型

所有记忆类型共用 `MemoryItem` 作为存储载体，`content` 字段按类型携带不同的结构化数据：

```python
class MemoryItem(BaseModel):
    id: str
    memory_type: MemoryType          # session / episodic / semantic
    content: dict[str, Any]          # 类型相关的结构化数据
    embedding: list[float] | None   # 可选向量
    importance: float = 0.5         # [0, 1]
    timestamp: datetime
    ttl: int | None = None           # None = 永不过期
    metadata: dict[str, Any] = {}
```

各类型 `content` 的结构：

```python
# SessionMemory 的 content
{
    "session_id": "sess_xxx",
    "messages": [{"role": "user", "content": "..."}, ...],
    "context": {"key": "value"},
    "agent_state": {"step": 3, "status": "running"}
}

# EpisodicMemory 的 content
{
    "session_id": "sess_xxx",
    "agent_name": "analyst",
    "user_id": "user_01",
    "interaction_type": "query",
    "summary": "用户询问了...",
    "messages": [...],
    "outcome": "success"
}

# SemanticMemory 的 content
{
    "entity_type": "preference",
    "entity_name": "投资风格",
    "entity_properties": {"style": "保守"},
    # 或：
    "relation": {"source": "e_001", "target": "e_002", "type": "prefers"}
}
```

### 2.4 不重要原则（Trivial Principle）

并非所有数据都需要持久化。决策原则：

| 数据特性         | 举例               | 存储决定         |
| ---------------- | ------------------ | ---------------- |
| 高价值 + 低频率  | 用户决策、偏好变更  | 三种 Memory 都存  |
| 低价值 + 高频率  | 实时聊天流中间状态  | 只存 Session     |
| 高价值 + 高频率  | Agent 技能学习记录  | 聚合后存 Episodic |
| 低价值 + 低频率  | 系统运行状态        | 不存（走 Logging）|

### 2.5 遗忘策略

三层遗忘机制：

1. **TTL（Session 级）**：会话记忆固定时间后自动清除
2. **重要性衰减（Episodic 级）**：每次 Consolidation 运行时，所有记忆的 importance 乘以衰减系数；低于 `min_importance` 的标记为待清理
3. **数据上限淘汰（全局）**：当记忆总数超过 `max_episodic_count` 时，淘汰 importance 最低的条目

```python
class ForgetPolicy(BaseModel):
    """遗忘策略配置。"""

    # TTL 遗忘
    enable_ttl: bool = True

    # 重要性衰减
    enable_decay: bool = True
    decay_factor: float = 0.95      # 每日衰减
    min_importance: float = 0.1     # 低于此值可清理

    # 上限淘汰
    max_episodic_count: int = 10000
    max_semantic_entities: int = 50000
```

## 3. 后果

### 正面

- 统一数据模型降低了接口复杂度，上层只需理解 `MemoryItem`
- 分层持久化策略让每种记忆类型用最适合的存储
- 遗忘策略防止数据无限增长

### 负面

- `content` 字段的 dict 类型牺牲了部分类型安全（通过 Pydantic validator 补偿）
- 统一模型意味着某些类型专有的字段需要塞进 `content` 或 `metadata`
- Chroma + SQLite 双存储意味着数据一致性不是事务性的（但记忆系统可以容忍最终一致性）

### 风险

- 如果 `MemoryItem` 的 content 结构过度膨胀，可以考虑拆分为具体子类
- Chroma 文件损坏风险（通过定期备份 mitigation）

## 4. 理由

选择"统一模型 + 路由分发"而不是"三套独立接口"的原因：

1. **上层不关心底层**：Agent 调用 `memory.store(item)` 时不需要知道走的是 Chroma 还是 SQLite
2. **路由可扩展**：未来增加新的记忆类型（如"肌肉记忆"——Agent 的模型微调状态），只需新增一个 MemoryStore 实现
3. **统一运维**：Consolidation、备份、监控都可以在 Interface 层统一处理

## 5. 相关链接

- [RFC-002 §3.3](docs/rfc/002-memory-layer-architecture.md#33-模块说明)
- [RFC-002 §3.5.1](docs/rfc/002-memory-layer-architecture.md#351-核心抽象)
- [ADR-003: Memory Layer 技术选型](docs/adr/ADR-003-memory-layer-tech-stack.md)
