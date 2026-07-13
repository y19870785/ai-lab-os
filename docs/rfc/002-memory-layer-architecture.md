# RFC-002: Memory Layer Architecture

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **RFC 编号** | 002                                  |
| **标题**     | Memory Layer 架构设计                  |
| **状态**     | 草稿                                  |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 ADR** | ADR-003, ADR-004                     |

## 1. 背景

AI-Lab 现有的四层架构（Core → Knowledge → Agent → Application）中，缺少一个关键的中间层：**Memory Layer**。

当前，Agent 没有"记忆能力"：
- 每次会话是独立的，Agent 不记得之前的交互
- 用户偏好、历史决策、Agent 经验无法跨会话复用
- 系统没有统一的"遗忘"机制，数据只增不减
- Knowledge Layer 处理的是外部文档知识，不处理系统自身的交互记忆

Memory Layer 的定位是填补 Core 和 Knowledge 之间的空白：

```
Core Layer         Memory Layer          Knowledge Layer
(基础设施)          (系统记忆)             (外部知识)
                    ↕
               Agent Layer
```

从另一个维度看，Memory Layer 是 AI-Lab 的"记忆系统"，类比人类记忆的分层模型：

| 记忆类型     | 对应层      | 特征                       | 实现技术               |
| ------------ | ----------- | -------------------------- | ---------------------- |
| 工作记忆     | Core 短期   | 当前会话上下文，易失         | Redis / 内存 Dict      |
| 情景记忆     | Memory      | 历史会话、交互记录，可检索   | Vector DB + SQL        |
| 语义记忆     | Memory      | 概念关系、用户偏好，结构化   | Graph DB / KV Store    |
| 程序记忆     | Memory      | Agent 技能记忆、流程模板     | SQL + Embedding        |
| 外部知识     | Knowledge   | 文档、网页、外部数据源       | RAG + Vector DB        |

## 2. 目标

- 定义 Memory Layer 的定位、职责和与相邻层（Core / Knowledge / Agent）的边界
- 设计统一记忆接口：写（存储/更新/遗忘）和读（检索/回忆/关联）
- 设计记忆的持久化、过期和优先级机制
- 明确 Memory Layer 的包结构和核心数据模型
- **不在此次范围**：Knowledge Layer 的具体实现、Agent 层的记忆消费逻辑

## 3. 设计方案

### 3.1 整体思路

Memory Layer 采用**分层记忆结构**，分为三个子系统：

1. **Session Memory（会话记忆）**：短期，当前运行中的上下文
2. **Episodic Memory（情景记忆）**：长期，历史交互记录
3. **Semantic Memory（语义记忆）**：长期，结构化概念和关系

三个子系统共用同一套抽象接口（`MemoryStore`），但实现策略不同。

### 3.2 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         Memory Layer                              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Memory Interface                          │ │
│  │  ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌───────────────┐  │ │
│  │  │  Store  │ │  Recall  │ │  Forget   │ │  Consolidate  │  │ │
│  │  │ (写入)  │ │ (检索)    │ │ (遗忘)     │ │ (记忆整合)     │  │ │
│  │  └────┬────┘ └────┬─────┘ └─────┬──────┘ └───────┬───────┘  │ │
│  └───────┼────────────┼─────────────┼────────────────┼──────────┘ │
│          │            │             │                │            │
│  ┌───────┴────────────┴─────────────┴────────────────┴──────────┐ │
│  │                 Memory Store Abstraction                     │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │ │
│  │  │  KVStore     │ │  VectorStore │ │  GraphStore         │ │ │
│  │  │ (键值存储)    │ │ (向量存储)    │ │ (图存储: 关系/概念)  │ │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘ │ │
│  └─────────┼────────────────┼────────────────────┼──────────────┘ │
│            │                │                    │                │
└────────────┼────────────────┼────────────────────┼────────────────┘
             │                │                    │
    ┌────────┴────┐   ┌──────┴──────┐   ┌─────────┴─────────┐
    │  Redis      │   │  Chroma     │   │  SQLite /         │
    │  (内存 KV)  │   │  (向量 DB)   │   │  NetworkX (图)    │
    └─────────────┘   └─────────────┘   └───────────────────┘
                     Core Layer 提供抽象接口
```

### 3.3 模块说明

#### 模块 1：Memory Interface（统一入口）

**职责**：对外提供统一的记忆操作入口，屏蔽底层存储差异。

```python
class MemoryInterface:
    """Memory Layer 的统一入口。Agent 和上层通过此接口访问记忆。"""

    # === 写操作 ===
    async def store(self, memory: MemoryItem) -> str: ...
    async def update(self, memory_id: str, data: dict) -> None: ...
    async def delete(self, memory_id: str) -> None: ...

    # === 读操作 ===
    async def recall(
        self, query: RecallQuery, top_k: int = 10
    ) -> list[MemoryItem]: ...

    async def get_context(
        self, session_id: str, context_type: ContextType
    ) -> Context: ...

    # === 维护操作 ===
    async def forget(
        self, policy: ForgetPolicy
    ) -> int: ...  # 返回遗忘条目数
    async def consolidate(self) -> ConsolidationReport: ...
```

#### 模块 2：Session Memory（会话记忆）

**职责**：保存当前活跃会话的上下文，生命周期和会话绑定。

**特征**：
- TTL 驱动过期：会话结束后自动清理
- 存储内容：对话历史、当前 Agent 状态、临时变量
- 后端：Redis（with TTL）或内存 Dict

**数据模型**：

```python
class SessionMemory(BaseModel):
    """会话记忆。"""
    session_id: str
    messages: list[Message]
    context: dict[str, Any]       # 当前上下文变量
    agent_state: dict[str, Any]   # Agent 内部状态快照
    created_at: datetime
    ttl: int = 3600               # 默认 1 小时过期
```

#### 模块 3：Episodic Memory（情景记忆）

**职责**：长期存储历史交互记录，支持语义检索和回顾。

**特征**：
- 每次 Agent 交互完成后自动持久化
- 存储时自动生成 embedding，支持语义检索
- 支持时间范围过滤 + 语义相似度混合检索
- 遗忘策略：重要性评分 + 时间衰减

**数据模型**：

```python
class EpisodicMemory(BaseModel):
    """情景记忆——一次完整的交互记录。"""
    id: str                       # UUID
    session_id: str
    agent_name: str
    user_id: str
    interaction_type: str          # "query" / "task" / "decision"
    summary: str                   # 自动生成的交互摘要
    embedding: list[float]         # summary 的向量
    messages: list[Message]        # 完整交互记录
    outcome: str | None            # 结果评估（成功/失败/部分成功）
    importance: float = 0.5       # 重要性评分 [0, 1]
    timestamp: datetime
    expire_at: datetime | None     # 过期时间（None 表示永不过期）
```

#### 模块 4：Semantic Memory（语义记忆）

**职责**：存储结构化的概念、实体及其关系，构建系统内部的"知识图谱"。

**特征**：
- 以实体（Entity）和关系（Relation）为核心
- 支持图遍历检索（如"用户 U 偏好的投资策略有哪些？"）
- 从 Episodic Memory 中自动抽取和更新
- 实现方式：先用关系型 SQL（实体表 + 关系表），后续可升级到真正的图数据库

**数据模型**：

```python
class Entity(BaseModel):
    """语义实体。"""
    id: str
    type: str                      # "user" / "preference" / "concept" / "strategy"
    name: str
    properties: dict[str, Any]
    embedding: list[float] | None
    created_at: datetime
    updated_at: datetime

class Relation(BaseModel):
    """实体间关系。"""
    id: str
    source_id: str
    target_id: str
    relation_type: str             # "prefers" / "belongs_to" / "derived_from"
    weight: float = 1.0           # 关系强度
    properties: dict[str, Any]
    created_at: datetime
```


#### 模块 4：Decision Memory（决策记忆）

**职责**：记录和检索 Agent 的关键决策过程——不仅记录"做了什么决定"，还记录"为什么做这个决定"。

**特征**：
- 每次 Agent 做出重要决策时自动写入（基于配置的重要性阈值）
- 包含完整的推理链：面临的选择、各选项的评估、最终选择、选择理由
- 与 Episodic Memory 关联：记录是哪个交互触发了这个决策
- 支持结果追踪：决策被执行后，记录实际结果（成功/失败/意外）
- 受 Memory Layer 的遗忘策略管理（重要性衰减 + 上限淘汰）

**数据模型**：

```python
class DecisionMemory(BaseModel):
    """决策记忆——一次完整的决策记录。"""
    id: str                       # UUID
    session_id: str               # 关联的会话
    agent_name: str               # 做出决策的 Agent
    user_id: str                  # 决策关联的用户

    # 决策上下文
    trigger: str                  # 触发决策的场景描述
    context: dict[str, Any]       # 决策时的系统状态快照

    # 决策过程
    alternatives: list[DecisionAlternative]  # 备选方案
    chosen: str                   # 最终选择的方案名称
    reasoning_chain: list[ReasoningStep]     # 推理步骤链

    # 决策结果
    outcome: DecisionOutcome | None = None   # 决策结果
    outcome_summary: str | None = None       # 结果摘要

    # 元数据
    importance: float = 0.5       # 决策重要性 [0, 1]
    confidence: float = 0.7       # 决策时的置信度
    tags: list[str] = []
    timestamp: datetime
    expire_at: datetime | None = None


class DecisionAlternative(BaseModel):
    """决策备选方案。"""
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    estimated_impact: str | None = None


class ReasoningStep(BaseModel):
    """推理步骤——决策过程的原子单位。"""
    order: int
    description: str               # 推理步骤描述
    evidence: list[str] = []       # 依据的来源
    conclusion: str | None = None  # 此步骤的中间结论


class DecisionOutcome(str, Enum):
    """决策结果分类。"""
    SUCCESS = "success"            # 达到预期
    PARTIAL = "partial"            # 部分达成
    FAILURE = "failure"            # 未达预期
    PENDING = "pending"            # 结果未明
    OVERTURNED = "overturned"      # 后续被推翻
```

**与 Episodic Memory 的区别**：

| 维度         | Episodic Memory          | Decision Memory          |
| ------------ | ------------------------ | ------------------------ |
| 记录粒度     | 整次交互（对话/任务）      | 单个决策点                |
| 内容核心     | 对话内容、任务上下文       | 推理链、备选方案、选择理由 |
| 写入条件     | 每次交互自动写入           | 仅重要决策时写入          |
| 检索方式     | 语义向量检索               | 时间线 + 决策类型 + 重要性 |
| 典型用途     | "用户上次问了什么"         | "用户上次为什么做这个选择" |
| 关联         | 可引用多个 Decision        | 属于一个 Episodic         |

**与 Knowledge Layer DecisionKnowledge 的边界**：

| 维度         | Decision Memory（系统记忆）   | DecisionKnowledge（外部知识）  |
| ------------ | --------------------------- | ----------------------------- |
| 创建者       | 系统自动记录                  | 用户手动管理                   |
| 生命周期     | 受遗忘策略管理（自动衰减删除）   | 用户决定保留与否                |
| 置信度       | 运行时中等置信度（0.7）        | 用户验证后高置信度（1.0）       |
| 编辑         | 只追加不可修改                 | 可编辑、版本管理                |
| 升级路径     | Agent/用户可"推送"到 Knowledge | 从 Memory 升级而来的正式记录    |


#### 模块 5：Consolidation Engine（记忆整合引擎）

**职责**：定期执行记忆维护任务，包括：
- **摘要聚合**：多条相似情景记忆合并为一条摘要
- **重要性重估**：根据后续交互重新计算记忆重要性
- **遗忘执行**：根据策略删除低价值记忆
- **语义抽取**：从情景记忆中自动提取实体和关系

```python
class ConsolidationPolicy(BaseModel):
    """记忆整合策略配置。"""
    schedule: str = "daily"        # 执行频率
    similarity_threshold: float = 0.85  # 相似度阈值
    importance_decay: float = 0.95 # 每日衰减系数
    max_episodic_count: int = 10000 # 情景记忆上限
    min_importance: float = 0.1    # 遗忘阈值
```

### 3.4 数据流

**典型流程：Agent 完成一次交互后的记忆写入**

```
Agent Run (交互完成)
    │
    ▼
Agent Layer 调用 MemoryInterface.store()
    │
    ├──→ Session Memory: 更新当前会话上下文
    │
    ├──→ Episodic Memory:
    │     1. 生成 summary（LLM 摘要）
    │     2. 计算 embedding
    │     3. 评估 importance
    │     4. 持久化到 Vector Store
    │
    ├──→ Decision Memory:
    │     (如果交互中包含决策点)
    │     1. 检测决策事件
    │     2. 提取推理链、备选方案
    │     3. 评估重要性并写入
    │
    └──→ Semantic Memory:
          1. 从交互中提取实体（用户偏好、提及的概念）
          2. 创建/更新 Entity 和 Relation
          3. 持久化到关系存储
```

**典型流程：Agent 启动时加载相关记忆**

```
Agent Start (新任务)
    │
    ▼
Agent Layer 调用 MemoryInterface.recall()
    │
    ├──→ Session Memory: 加载当前会话上下文（如果有）
    │
    ├──→ Episodic Memory:
    │     1. 用任务描述生成 query embedding
    │     2. 向量检索 top-k 相似历史交互
    │     3. 时间过滤 + 重要性排序
    │     4. 返回相关记忆片段
    │
    └──→ Semantic Memory:
          1. 提取任务中的关键实体
          2. 图遍历检索关联实体和关系
          3. 返回上下文知识
    │
    ▼
Agent Layer 整合 → 注入 Prompt
```

### 3.5 接口定义

#### 3.5.1 核心抽象

```python
class MemoryStore(ABC):
    """记忆存储的底层抽象。所有具体实现（KV / Vector / Graph）都实现此接口。"""

    @abstractmethod
    async def save(self, item: MemoryItem) -> str: ...

    @abstractmethod
    async def batch_save(self, items: list[MemoryItem]) -> list[str]: ...

    @abstractmethod
    async def get(self, id: str) -> MemoryItem | None: ...

    @abstractmethod
    async def query(self, spec: MemoryQuery) -> list[MemoryItem]: ...

    @abstractmethod
    async def delete(self, id: str) -> bool: ...

    @abstractmethod
    async def count(self, filter: MemoryFilter | None = None) -> int: ...


class MemoryItem(BaseModel):
    """通用记忆条目。"""
    id: str
    memory_type: MemoryType        # "session" / "episodic" / "semantic"
    content: dict[str, Any]
    embedding: list[float] | None
    importance: float = 0.5
    timestamp: datetime
    ttl: int | None = None         # None = 永不过期
    metadata: dict[str, Any] = {}


class MemoryQuery(BaseModel):
    """记忆检索参数。"""
    query_text: str | None = None
    query_embedding: list[float] | None = None
    memory_type: MemoryType | None = None
    filters: dict[str, Any] = {}   # 字段级过滤
    time_range: tuple[datetime, datetime] | None = None
    top_k: int = 10
    min_importance: float = 0.0
```

#### 3.5.2 与 Core Layer 的关系

Memory Layer 依赖 Core Layer 的基础设施：
- `core.data` → 底层存储抽象（Repository、Cache）
- `core.config` → 记忆策略配置
- `core.logging` → 链路追踪
- `core.bus` → 记忆事件（`memory.stored` / `memory.forgotten` / `memory.consolidated`）

Memory Layer **不依赖** Agent Layer 或 Knowledge Layer。

#### 3.5.3 包结构

```
memory/
├── __init__.py              # 导出 MemoryInterface
├── interface.py             # MemoryInterface 统一入口
├── protocol.py              # MemoryStore 抽象 + MemoryItem 等数据模型
├── session.py               # SessionMemory 实现（Redis / 内存）
├── episodic.py              # EpisodicMemory 实现（Vector Store）
├── semantic.py              # SemanticMemory 实现（关系存储）
├── decision.py              # DecisionMemory 实现（决策推理链存储）
├── consolidation.py         # ConsolidationEngine 实现
└── config.py                # Memory 配置模型
```

## 4. 可选方案

### 方案 A：嵌入 Core Layer 作为子模块（选定方案）

将 Memory Layer 作为 `core/memory/` 子包，放在 Core Layer 内部。

**优点**：
- 目录结构简单，减少顶层目录数量
- Memory 直接访问 Core Layer 的基础设施（Config、Data）
- Agent 导入路径短：`from core.memory import memory`

**缺点**：
- Core 的"core"语义扩大，从"基础设施"延伸到"记忆系统"
- Memory 有自己的业务逻辑（整合、遗忘、重要性评估），不是纯粹基础设施

### 方案 B：独立的 memory/ 顶层包

将 Memory Layer 作为与 `core/` 同级的 `memory/` 目录。

**优点**：
- 职责边界清晰，Core 是基础设施，Memory 是系统记忆
- 方便未来独立演进和替换

**缺点**：
- Memory 强依赖 Core，但又不属于 Common Layer，放在顶层会混淆架构层级
- 导入路径变长，需要 `from memory import ...`
- 与其他层（Knowledge、Agent）的对齐关系不直观

### 选型理由

选择**方案 A**，原因：
1. **实用主义**：当前阶段，Memory Layer 和 Core Layer 的交互极为频繁（每个操作都要经过 Config、Data、Logging），放在一起降低耦合复杂度
2. **认知成本**：`core.memory` 读起来就是"核心的记忆系统"，语义清晰
3. **重构成本低**：如果后续 Memory Layer 成长为独立的服务，提取到 `memory/` 顶层只是目录移动 + 导入路径更新

### 特殊说明：Semantic Memory 的 Schema 先行

Semantic Memory 的 Entity-Relation 模型虽然需要图数据库的能力，但 Phase 1 先用 SQLite 做关系存储：

```
entity 表：id, type, name, properties(JSON), embedding(BLOB), timestamps
relation 表：id, source_id, target_id, relation_type, weight, properties(JSON)
```

这样在 Phase 1 就有可工作的 Semantic Memory，后续切换到 Neo4j 或类似方案时只需替换存储后端。

## 5. 影响分析

| 维度       | 影响说明                                         |
| ---------- | ------------------------------------------------ |
| 性能       | 记忆检索增加 Agent 启动延迟（~50-200ms 向量检索）；Consolidation 为后台异步任务 |
| 存储       | 新增向量存储（Chroma 本地文件）；SQLite 语义存储；Redis 可选用于会话记忆 |
| 安全       | 记忆数据含用户交互历史，需隔离用户级记忆空间        |
| 可维护性   | 统一 MemoryInterface 入口，切换后端无需改上层代码    |
| 依赖变更   | 新增依赖：chromadb（向量）、numpy（embedding 计算） |

## 6. 实施计划

### Phase 1.2a：Memory Layer 基础（当前 RFC 对应的实施步骤）

1. 创建 `core/memory/` 子包及所有模块骨架
2. 实现 `protocol.py`：MemoryStore 抽象 + MemoryItem 等数据模型
3. 实现 `interface.py`：MemoryInterface 统一入口
4. 实现 `session.py`：基于 Dict 的 SessionMemory（Phase 1 内存版本）
5. 实现 `episodic.py`：基于 Chroma 的 EpisodicMemory
6. 实现 `config.py`：Memory 配置模型
7. 更新 `config/default.yaml`：加入 Memory 配置段
8. 编写 Memory Layer 单元测试

### Phase 1.2b：Semantic Memory + Consolidation

1. 实现 `semantic.py`：基于 SQLite 的 Entity-Relation 存储
2. 实现 `consolidation.py`：记忆整合引擎（摘要聚合 + 重要性衰减 + 遗忘执行）
3. 集成测试：完整的记忆写入 → 检索 → 整合 → 遗忘链路

### 验收标准

- [ ] MemoryInterface 提供 store / recall / forget / consolidate 四个核心操作
- [ ] SessionMemory 支持 TTL 过期自动清理
- [ ] EpisodicMemory 支持语义向量检索 + 时间过滤
- [ ] SemanticMemory 支持 Entity 创建、关系查询和图遍历
- [ ] DecisionMemory 支持决策记录存储、推理链检索和结果追踪
- [ ] ConsolidationEngine 支持重要性衰减和过期清理
- [ ] 所有模块有单元测试覆盖核心路径
- [ ] 无循环导入

## 7. 相关文档

- [RFC-001: Core Layer Architecture](docs/rfc/001-core-layer-architecture.md)
- [ADR-001: Core Layer 包结构](docs/adr/ADR-001-core-layer-package-structure.md)
- [ADR-003: Memory Layer 技术选型](docs/adr/ADR-003-memory-layer-tech-stack.md)
- [ADR-004: Memory 数据模型与持久化](docs/adr/ADR-004-memory-data-model.md)
