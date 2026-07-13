# AI-Lab Architecture

## 整体架构

采用 **Governance + Core + Memory + Knowledge + Agent + Application** 六层架构。

```
┌───────────────────────────────────────────────────────────┐
│            Governance Layer (治理层)                       │
│  项目上下文 · 开发策略 · Agent 策略 · 知识策略             │
│  模型策略 · 版本策略                                       │
├───────────────────────────────────────────────────────────┤
│               Application Layer (业务应用层)                │
│  Investment Office · Enterprise AI · Quotation System      │
├───────────────────────────────────────────────────────────┤
│                 Agent Layer (智能 Agent 层)                 │
│  Analyst · Secretary · Research · Workflow                 │
├───────────────────────────────────────────────────────────┤
│               Knowledge Layer (知识系统层)                  │
│  RAG · Document Management · External Data Sources         │
├───────────────────────────────────────────────────────────┤
│                Memory Layer (记忆系统层)                    │
│  Session Memory · Episodic Memory · Semantic Memory         │
├───────────────────────────────────────────────────────────┤
│                Core Layer (基础能力层)                      │
│  配置 · 日志 · 消息总线 · 数据访问 · Agent 管理 · 身份管理  │
└───────────────────────────────────────────────────────────┘
```

### 各层职责

| 层级        | 职责                                 | 核心模块                                        |
| ----------- | ------------------------------------ | ----------------------------------------------- |
| Governance  | 跨层治理：定义规则和约束               | 6 个策略文件（开发/Agent/知识/模型/版本）         |
| Core        | 基础设施：被所有上层依赖               | Config / Logging / Message Bus / Data / Identity |
| Memory      | 系统记忆：保存交互历史、偏好、知识结构   | Session / Episodic / Semantic Memory             |
| Knowledge   | 外部知识：接入和管理外部文档与数据源     | RAG / Vector DB / Document Manager               |
| Agent       | 智能体：执行分析、秘书、研究等任务      | Analyst / Secretary / Research / Workflow        |
| Application | 业务应用：面向用户的产品功能            | Investment Office / Enterprise AI                |

### 层间依赖规则

- **下层不依赖上层**：Core 不知道 Memory 的细节，Memory 不知道 Knowledge 的细节
- **上层可依赖下层**：Agent 可使用 Core、Memory、Knowledge 的所有能力
- **同层模块间通过 Message Bus 解耦**
- **不允许跨层依赖**：Application 不可直接依赖 Core

## Governance Layer

### 定位

Governance Layer 不是传统的"业务层"，而是跨层的治理体系——类似操作系统的"内核参数"和"安全策略"。
它不提供业务功能，而是定义所有层必须遵守的规则和约束。

### 与其它层的关系

- Governance Layer **不直接参与**数据流或业务逻辑
- Governance Layer 的规则通过**文档约束**和**代码检查**（CI）执行
- 所有层的架构设计必须遵循 Governance Layer 定义的策略

### 覆盖范围

| 策略文件 | 核心内容 | 约束对象 |
| --- | --- | --- |
| [PROJECT_CONTEXT.md](../governance/PROJECT_CONTEXT.md) | 项目使命、愿景、路线图 | 所有贡献者 |
| [DEVELOPMENT_POLICY.md](../governance/DEVELOPMENT_POLICY.md) | RFC/ADR 流程、提交规范、分支策略 | 所有代码变更 |
| [AGENT_POLICY.md](../governance/AGENT_POLICY.md) | Agent 创建流程、命名、权限、生命周期 | Agent Layer |
| [KNOWLEDGE_POLICY.md](../governance/KNOWLEDGE_POLICY.md) | 知识分类、审计、版本、可信度 | Knowledge Layer |
| [MODEL_POLICY.md](../governance/MODEL_POLICY.md) | 模型抽象、Provider 接口、成本控制 | 所有使用模型的地方 |
| [VERSIONING_POLICY.md](../governance/VERSIONING_POLICY.md) | 版本号、架构升级、数据迁移 | 全项目 |

详见 [docs/governance/](../governance/) 目录。

---


## Core Layer

### 职责

提供所有上层模块依赖的基础设施。微内核设计，模块间通过接口解耦。

### 模块结构

```
core/
├── config.py            # Config Manager（分层配置，热加载）
├── logging.py           # Logging System（结构化 JSON + LogContext）
├── bus/                 # Message Bus（异步通信）
│   ├── event.py         #   Event / Task 数据模型
│   ├── protocol.py      #   Publisher / Subscriber / TaskQueue / MessageBus 抽象
│   ├── publisher.py     #   MemoryPublisher 实现（并发分发）
│   ├── subscriber.py    #   MemorySubscriber 实现（订阅管理）
│   ├── queue.py         #   MemoryTaskQueue 实现（超时 + 重试）
│   ├── bus.py           #   MemoryBus 组合实现 + 全局单例
│   └── memory_events.py #   Memory 事件类型常量
├── data/                # Data Access Layer（数据访问）
│   ├── protocol.py      #   Repository / Cache / API 抽象
├── agent/               # Agent Runtime（Agent 管理）
│   ├── protocol.py      #   AgentRuntime 抽象
│   └── models.py        #   AgentSpec / AgentInstance / AgentStatus
├── identity/            # Identity & Session（身份管理）
│   ├── protocol.py      #   IdentityManager 抽象
│   └── models.py        #   User / Session / Credentials
└── memory/              # Memory Layer（嵌入 Core 的记忆系统）
    ├── interface.py     #   MemoryInterface 统一入口
    ├── protocol.py      #   MemoryStore 抽象 + MemoryItem
    ├── session.py       #   SessionMemory（内存实现）
    ├── episodic.py      #   EpisodicMemory（Chroma 实现）
    └── config.py        #   Memory 配置模型
```

### 核心能力

- **配置管理**：分层覆盖（默认 → YAML → 环境变量 → 运行时），Pydantic 类型安全
- **日志系统**：结构化 JSON 输出，LogContext 自动注入 trace_id / agent_id / session_id
- **消息总线**：Event Bus（Pub-Sub）+ Task Queue 双模式，内存实现，支持超时/重试/钩子系统
- **数据访问**：Repository Pattern + Cache 抽象 + 外部 API 客户端
- **Agent 管理**：注册、生命周期、状态查询
- **身份管理**：API Key / JWT 认证，RBAC 授权

## Memory Layer

### 职责

管理 AI-Lab 的系统记忆，处于 Core 和 Knowledge 之间，类比人类记忆系统的分层结构。

### 四层记忆

| 记忆类型     | 对应层      | 特征                     | Phase 1 存储 |
| ------------ | ----------- | ------------------------ | ------------ |
| Session      | 短期        | 当前会话上下文，TTL 过期   | 内存 Dict    |
| Episodic     | 长期        | 历史交互记录，语义检索     | Chroma       |
| Semantic     | 长期        | 实体关系知识，结构化查询   | SQLite       |
| Decision     | 长期        | 决策推理链与结果追踪      | SQLite + Chroma |

### 核心接口

```python
# 统一入口
memory = MemoryInterface()

# 写入
await memory.store(MemoryItem(memory_type=MemoryType.EPISODIC, content={...}))
await memory.update(memory_id, MemoryType.SESSION, {"key": "value"})
await memory.store(MemoryItem(memory_type=MemoryType.DECISION, content={
    "trigger": "投资建议请求",
    "alternatives": [...],
    "reasoning_chain": [...],
    "chosen": "方案A",
}))

# 检索
results = await memory.recall(MemoryQuery(query_text="用户的偏好"))
decisions = await memory.recall(MemoryQuery(
    query_text="投资决策",
    memory_type=MemoryType.DECISION,
    filters={"outcome": "success"},
))

# 维护
await memory.delete(memory_id, MemoryType.EPISODIC)
count = await memory.count()
```

详见 [RFC-002: Memory Layer Architecture](docs/rfc/002-memory-layer-architecture.md)。

## Knowledge Layer

## Knowledge Layer

### 职责

外部知识系统层，负责接入、管理、检索所有外部知识。
采用**知识类型驱动**设计，五种知识类型共用采集/检索基础设施，但各自独立存储和优化策略。

### 五种知识类型

| 知识类型     | 定义                       | 存储方式           | 检索方式               |
| ------------ | -------------------------- | ------------------ | ---------------------- |
| 文档知识     | 外部文档数据               | SQLite + Chroma    | 关键词 + 向量混合检索   |
| 实体知识     | 命名实体及属性             | SQLite + Chroma    | ID 查找 + 语义相似     |
| 关系知识     | 实体间语义关系             | SQLite (图结构)     | 图遍历                  |
| 经验知识     | Best Practice / 方法论     | SQLite + Chroma    | 语义检索               |
| 决策知识     | 历史决策及推理过程          | SQLite + Chroma    | 语义检索 + 时间线过滤   |

### 核心流程

```
原始数据（文件/URL/API）
    │
    ▼
Ingestion Pipeline
    │
    ├─→ Extractor（提取文本+元数据）
    ├─→ Chunker（按策略切割：递归/固定/Markdown）
    ├─→ Entity Extractor（实体识别，可选）
    └─→ Embedder（向量化）
    │
    ▼
存储层（SQLite + Chroma + 文件系统）
    │
    ▼
Retrieval Engine（分层检索）
    ├─→ Level 1: 关键词精确匹配（FTS5）
    ├─→ Level 2: 向量语义检索（Chroma）
    ├─→ Level 3: 图遍历（SQLite 递归 CTE）
    └─→ Level 4: 混合检索（RRF 融合 + 可选重排序）
```

### 模块结构

```
knowledge/
├── __init__.py          # 包入口
├── manager.py          # KnowledgeManager 统一入口
├── ingestion.py        # IngestionPipeline
├── retrieval.py        # RetrievalEngine
├── permission.py       # 知识权限模型
├── config.py           # Knowledge Layer 配置
├── models/             # 五种知识数据模型
│   ├── document.py     # DocumentKnowledge / Chunk
│   ├── entity.py       # EntityKnowledge / RelationKnowledge
│   └── experience.py   # ExperientialKnowledge / DecisionKnowledge
├── chunking/           # 切割策略
│   ├── protocol.py     # ChunkStrategy 抽象
│   ├── recursive.py    # 递归分割
│   ├── fixed_size.py   # 固定大小
│   └── markdown.py     # Markdown 结构
├── embedding/          # Embedding 接口
│   ├── protocol.py     # EmbeddingProvider 抽象
│   └── provider_none.py# 降级实现
└── storage/            # 存储层抽象
    └── protocol.py     # KnowledgeStore / VectorStore / GraphStore
```

详见 [RFC-004: Knowledge Layer Architecture](docs/rfc/004-knowledge-layer-architecture.md)。


## Agent Layer

### 职责

智能 Agent 层，承载 AI-Lab 所有 Agent 的定义、编排和执行。
采用**身份驱动 + 能力组合**的设计：每个 Agent 有明确的身份声明，能力由注册的 Tool 和绑定的 Memory 共同定义。

### 设计核心

```
Agent = AgentIdentity + [Tools] + [MemoryProfile] + [AgentPermission]
```

**Agent Identity（身份声明）：** 每个 Agent 有明确的身份——名字、角色、能力清单。
**Agent Role（角色分类）：** 预定义 8 种角色（Analyst / Secretary / Researcher / Assistant / Operator / Workflow / Critic / Orchestrator），支持自定义扩展。
**Tool System（工具系统）：** 标准化工具接口，支持注册、发现、执行、审计。工具是 Agent 与外部世界交互的唯一通道。
**Memory Association（记忆关联）：** 每个 Agent 通过 MemoryProfile 声明需要的记忆类型和使用策略。启动时自动加载相关记忆注入 Prompt。
**Permission Model（权限模型）：** 双层权限检查——Agent 自身能力边界 × 用户授权范围。
**Agent Protocol（Agent 间通信）：** 基于 Message Bus 构建，定义委托 / 查询 / 通知 / 广播 / 协调 等标准化消息语义。
**Lifecycle（生命周期）：** 从 Defined → Initialized → Active → Running/Paused → Disabled → Retired 的完整状态机。

### 模块结构

```
agents/
├── __init__.py          # Agent Layer 入口
├── identity.py          # AgentIdentity / AgentRole / CapabilityDecl
├── permission.py        # AgentPermission / AuditLevel
├── memory.py            # MemoryProfile
├── lifecycle.py         # AgentLifecycleManager + 状态机
├── protocol.py          # AgentMessage / Agent Protocol
├── context.py           # AgentTask / AgentResult
├── config.py            # Agent Layer 配置
├── tools/               # 工具系统
│   ├── __init__.py
│   ├── protocol.py      # Tool / ToolCall / ToolHandler
│   └── registry.py      # ToolRegistry
└── roles/               # 角色模板
    ├── __init__.py
    └── registry.py      # RoleRegistry + 预定义模板
```

### 核心业务流程

```
用户通过 Application 提交任务
    │
    ▼
Agent Scheduler → 路由到目标 Agent Instance
    │
    ├──→ 加载 Memory（按 MemoryProfile：Session + 相关 Episodic）
    │
    ├──→ 进入思考循环
    │     Brain → 调用 Tool → 获得结果 → 继续 → 完成
    │
    ├──→ 与其他 Agent 协作（按需，通过 Agent Protocol）
    │
    └──→ 写入 Episodic Memory → 返回结果
```

详见 [RFC-003: Agent Architecture](docs/rfc/003-agent-architecture.md)。

## Application Layer

> 待设计（Phase 2.1）

---

## 架构原则

1. **模块化** — 每层独立，可替换
2. **API First** — 层间通过明确定义的接口通信
3. **配置驱动** — 避免硬编码，环境分离，热加载
4. **可观测性** — 日志/指标/链路追踪
5. **文档先行** — 重大变更先写 RFC，架构决策记录 ADR
6. **实用主义** — Phase 1 追求可工作 > 过度抽象

