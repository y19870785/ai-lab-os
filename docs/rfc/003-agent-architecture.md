# RFC-003: Agent Architecture

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **RFC 编号** | 003                                  |
| **标题**     | Agent Layer 架构设计                   |
| **状态**     | 草稿                                  |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 ADR** | ADR-005, ADR-006, ADR-007            |

## 1. 背景

AI-Lab 五层架构中，Agent Layer 是核心智能层——它承载了所有"思考"和"执行"的逻辑。但当前 `core/agent/` 只定义了最基础的运行时管理（注册/启动/停止），远不足以支撑真正的智能 Agent 系统。

**当前问题：**
- Agent 没有"身份"概念——所有 Agent 只是 Core Runtime 管理的一串实例，无法区分"这是 Analyst Agent"还是"这是 Secretary Agent"
- Agent 没有"角色"系统——不同业务场景需要不同的行为模式和权限边界
- Agent 没有"工具"协议——Agent 可以做什么（查知识库、写文件、调 API）没有标准化
- Agent 没有"权限"模型——Agent 能访问哪些数据、调用哪些功能没有细粒度控制
- Agent 与 Memory 的关联是隐式的——Agent "记得什么"没有明确定义
- Agent 间协作没有标准协议——只能通过 Message Bus 发送原始 Event/Task，缺少 Agent 间通信语义

**Phase 1.3 的目标**：设计 Agent Layer 的完整架构，定义 Agent 身份模型、角色系统、工具协议、权限模型、记忆关联和生命周期管理。**不实现业务 Agent**。

## 2. 目标

- 定义 Agent 身份模型：Agent 的 Who / What / How
- 设计角色系统：预定义角色 + 自定义角色
- 设计工具系统：Tool 的注册、发现、执行协议
- 设计权限模型：Agent 维度 + 用户维度的双层访问控制
- 定义 Agent-Memory 关联：Agent 如何声明和使用记忆
- 定义 Agent 间协作协议：消息路由、任务委派、结果回调
- 明确 Agent Layer 的包结构和与 Core/Memory/Knowledge 层的边界
- **不在此次范围**：任何具体 Agent 的实现（Analyst、Secretary 等），Knowledge Layer 的实现

## 3. 设计方案

### 3.1 整体思路

Agent Layer 采用 **身份驱动 + 能力组合** 的设计哲学：

1. **身份（Identity）**：每个 Agent 有一个明确的身份声明——它是什么类型的 Agent，属于哪个角色，拥有什么能力
2. **能力（Capability）**：Agent 的能力由它注册的 Tools + 它绑定的 Memory 共同定义
3. **角色（Role）**：角色是身份和能力的预定义模板——"Analyst" = 数据分析能力 + 数据访问权限 + 对应记忆模板
4. **协作（Collaboration）**：Agent 间通过 Agent Protocol（基于 Message Bus 的更高层协议）协作

核心设计模式：**Agent = Identity + [Tools] + [Memory Access] + [Permissions]**

### 3.2 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                          Agent Layer                              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                     Agent Registry                           │ │
│  │  管理所有 Agent 类型定义、版本、角色映射                       │ │
│  └──────────┬───────────────────────────────────┬───────────────┘ │
│             │                                   │                 │
│  ┌──────────┴──────────┐     ┌──────────────────┴──────────────┐ │
│  │    Agent Instance   │     │       Agent Scheduler           │ │
│  │   (运行中的 Agent)   │     │   (任务路由 / 优先级 / 并发)    │ │
│  └──────────┬──────────┘     └──────────────────┬──────────────┘ │
│             │                                   │                 │
│  ┌──────────┴───────────────────────────────────┴──────────────┐ │
│  │               Agent 内部架构（每个 Instance）                 │ │
│  │                                                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │ │
│  │  │ Identity │  │  Brain   │  │  Tools   │  │  Memory    │  │ │
│  │  │ (身份)   │  │ (思考)    │  │ (工具)   │  │ (记忆)     │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │ │
│  │                                                             │ │
│  │  ┌──────────┐  ┌──────────────────────────────────────────┐ │ │
│  │  │ Context  │  │         Message Handler                  │ │ │
│  │  │ (上下文)  │  │   Agent Protocol 通信 / 事件处理         │ │ │
│  │  └──────────┘  └──────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Agent Protocol                             │ │
│  │   Agent 间通信协议：委托 / 查询 / 通知 / 广播 / 结果回调     │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
         │                 │                  │
         ▼                 ▼                  ▼
    Core Layer        Memory Layer      Knowledge Layer
    (基础设施)         (系统记忆)         (外部知识)
```

### 3.3 模块说明

#### 模块 1：Agent Identity（Agent 身份模型）

**职责**：定义 Agent 的身份声明——Agent 是谁、能做什么、怎么对外展现。

这是 Agent Layer 最核心的模块。身份模型是 Agent 的"元数据护照"。

```python
class AgentIdentity(BaseModel):
    """Agent 身份声明。

    描述一个 Agent 的核心身份特征。
    区别于 Core AgentSpec（技术描述），这里是"语义身份"。
    """
    agent_id: str                     # 全局唯一 ID
    name: str                         # 人类可读名称，如 "行业分析师"
    role: AgentRole                   # 角色分类
    description: str = ""             # 自然语言描述

    # 能力声明
    capabilities: list[CapabilityDecl] = []

    # 身份元数据
    version: str = "1.0.0"
    owner: str = "system"             # 创建者（user_id / "system"）
    tags: list[str] = []              # 自由标签，用于发现和路由
    avatar: str | None = None         # 标识图标/emoji

    # 运行时元数据（由系统填充）
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentRole(str, Enum):
    """Agent 角色分类。

    角色定义了 Agent 的行为模式和职责边界。
    """
    # 核心生产力角色
    ANALYST = "analyst"               # 数据分析与报告
    SECRETARY = "secretary"           # 日程管理与提醒
    RESEARCHER = "researcher"         # 信息调研与整理

    # 执行角色
    ASSISTANT = "assistant"           # 通用助手
    OPERATOR = "operator"             # 自动化执行
    WORKFLOW = "workflow"             # 工作流编排

    # 辅助角色
    CRITIC = "critic"                 # 审核与纠错
    ORCHESTRATOR = "orchestrator"     # 多 Agent 协调

    # 自定义（允许用户扩展）
    CUSTOM = "custom"
```

#### 模块 2：Capability System（能力系统）

**职责**：定义 Agent 的能力声明——Agent 能做什么、不能做什么。

能力是 Agent 的"技能清单"，由两部分组成：
1. **工具能力（Tool）**：Agent 能调用的外部功能（搜索、计算、写文件……）
2. **内在能力（Skill）**：Agent 自身具备的分析、推理、生成能力

```python
class CapabilityDecl(BaseModel):
    """能力声明。描述 Agent 的一项具体能力。"""
    name: str                         # "web_search"
    type: CapabilityType              # tool / skill / knowledge
    description: str = ""             # 自然语言描述
    config: dict[str, Any] = {}       # 能力特定配置


class CapabilityType(str, Enum):
    """能力类型。"""
    TOOL = "tool"                     # 外部工具（API 调用、文件操作等）
    SKILL = "skill"                   # 内在技能（分析、总结、翻译等）
    KNOWLEDGE = "knowledge"           # 知识域（特定领域的知识能力）
```

#### 模块 3：Tool System（工具系统）

**职责**：提供 Agent 可调用的标准化工具接口，支持工具的注册、发现和执行。

工具是 Agent 与外部世界交互的唯一通道。类比人类使用工具：

```
Agent (思考) → 决定用哪个工具 → 调用 Tool → 获得结果 → 继续思考
```

```python
class Tool(BaseModel):
    """工具定义。描述 Agent 可以用什么工具。"""
    name: str                         # "web_search"
    description: str                  # 工具用途描述，供 LLM 理解
    version: str = "1.0.0"

    # 接口定义
    parameters: JsonSchema            # 入参 JSON Schema
    returns: JsonSchema               # 出参 JSON Schema

    # 执行属性
    timeout: int = 30
    execution_type: ExecutionType     # sync / async / streaming
    requires_approval: bool = False   # 是否需要用户确认


class ExecutionType(str, Enum):
    """工具执行模式。"""
    SYNC = "sync"                     # 同步调用，等待结果
    ASYNC = "async"                   # 异步调用，通过回调获取结果
    STREAMING = "streaming"           # 流式返回


class ToolCall(BaseModel):
    """工具调用记录。"""
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    status: ToolCallStatus
    result: Any | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    token_cost: int = 0               # 此工具调用的 token 消耗


class ToolCallStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**Tool Registry**：全局工具注册中心，负责工具的注册、发现和版本管理。

```python
class ToolRegistry:
    """工具注册中心。管理所有可用工具。"""

    async def register(self, tool: Tool, handler: ToolHandler) -> None: ...
    async def unregister(self, tool_name: str) -> None: ...

    async def get_tool(self, tool_name: str) -> Tool | None: ...
    async def list_tools(self, filter: ToolFilter | None = None) -> list[Tool]: ...

    async def execute(self, call: ToolCall) -> ToolCallResult: ...
    async def execute_stream(self, call: ToolCall) -> AsyncIterator[ToolCallChunk]: ...


class ToolHandler(Protocol):
    """工具执行器的类型签名。"""
    async def __call__(self, arguments: dict[str, Any]) -> Any: ...
```

**预定义工具分类（组织约定，非强制）：**

| 工具类别     | 示例                          | 访问层级    |
| ------------ | ----------------------------- | ----------- |
| 读取工具     | knowledge_query, memory_read  | 低风险      |
| 写入工具     | memory_write, file_save       | 需要确认    |
| 执行工具     | code_execute, workflow_run    | 高风险/沙箱 |
| 通信工具     | notify_user, agent_message    | 审批        |
| 外部工具     | web_search, api_call          | 限流/隔离   |

#### 模块 4：Permission Model（权限模型）

**职责**：定义 Agent 能做什么、能访问什么。双层权限体系：

1. **Agent 级权限**：Agent 自身能调用哪些 Tools、访问哪些 Memory
2. **用户级权限**：Agent 代用户执行操作时，受用户权限约束

```python
class AgentPermission(BaseModel):
    """Agent 权限声明。

    双层检查：Agent 能做什么 × 用户授权 Agent 做什么。
    """
    agent_id: str

    # Layer 1：Agent 自身能力边界
    allowed_tools: list[str] = ["*"]       # 允许调用的工具列表
    blocked_tools: list[str] = []          # 禁止调用的工具列表
    allowed_memory_types: list[MemoryType] = [MemoryType.SESSION]

    # Layer 2：执行时的用户级约束
    require_user_approval: list[str] = []  # 需要用户确认的操作
    max_token_per_run: int = 100000        # 单次运行 token 上限
    allowed_hours: list[int] | None = None # 允许运行的时间段

    # 审计
    audit_level: AuditLevel = AuditLevel.BASIC
```

#### 模块 5：Memory Association（记忆关联）

**职责**：定义 Agent 如何声明和使用记忆——Agent 的"记忆声明"。

每个 Agent 可以声明它需要什么类型的记忆，以及记忆的使用策略。

```python
class MemoryProfile(BaseModel):
    """Agent 记忆画像。定义 Agent 如何使用记忆系统。"""
    agent_id: str

    # 声明需要哪些记忆
    enabled_memories: list[MemoryType] = [
        MemoryType.SESSION,
        MemoryType.EPISODIC,
    ]

    # 记忆检索策略
    recall_on_start: bool = True           # 启动时自动加载相关记忆
    max_recall_items: int = 20             # 单次最大召回数
    min_recall_importance: float = 0.3     # 最低重要性阈值

    # 记忆写入策略
    auto_store_episodic: bool = True       # 交互后自动写入情景记忆
    auto_extract_semantic: bool = False    # 是否自动提取语义实体

    # 上下文窗口管理
    max_context_tokens: int = 8000         # 注入 Prompt 的最大记忆 token 数
    context_ranking: str = "importance"    # 上下文排序方式
```

**Agent 启动时的记忆加载流程：**

```
Agent 收到任务
    │
    ▼
读取 MemoryProfile
    │
    ├──→ Session Memory: 加载当前会话（如果有）
    │
    ├──→ Episodic Memory: 按任务语义检索相关历史
    │     过滤：memory_type=EPISODIC, min_importance=0.3
    │     排序：按 relevance × importance 综合评分
    │     截断：最多 20 条，总计 ≤ 8000 tokens
    │
    └──→ Semantic Memory: 按任务实体检索关联知识
          过滤：与任务实体关联的 Entity-Relation
    │
    ▼
注入到 Agent 的 System Prompt
```

#### 模块 6：Agent Lifecycle（生命周期管理）

**职责**：定义 Agent 从创建到销毁的完整生命周期。

区别于 Core Layer 的 `AgentRuntime`（管理实例启停），这里是**业务生命周期**——包含身份注册、能力绑定、记忆初始化、权限配置等完整流程。

```
                      ┌─────────────┐
                      │  DEFINED    │  ← 身份注册，能力声明
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │  INITIALIZED│  ← 记忆初始化、权限绑定
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │   ACTIVE    │  ← 可接收任务
                      └──────┬──────┘
                         ┌───┴───┐
                         │       │
                  ┌──────▼──┐ ┌──▼───────┐
                  │ PAUSED  │ │  RUNNING │  ← 正在执行任务
                  └──────┬──┘ └──┬───────┘
                         │       │
                         └───┬───┘
                      ┌──────▼──────┐
                      │   ERROR     │  ← 异常状态
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │ DISABLED    │  ← 不可用
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │ RETIRED     │  ← 已退役，保留记录
                      └─────────────┘
```

```python
class AgentLifecycleState(str, Enum):
    """Agent 业务生命周期状态。"""
    DEFINED = "defined"               # 身份已注册
    INITIALIZED = "initialized"       # 能力/记忆/权限已绑定
    ACTIVE = "active"                 # 可接收任务
    RUNNING = "running"               # 正在执行任务
    PAUSED = "paused"                 # 暂停
    ERROR = "error"                   # 异常
    DISABLED = "disabled"             # 管理员禁用
    RETIRED = "retired"               # 已退役


class AgentLifecycleManager:
    """Agent 生命周期管理器。管理 Agent 的完整生命周期。"""

    async def define(self, identity: AgentIdentity) -> str: ...
    async def initialize(self, agent_id: str) -> None: ...
    async def activate(self, agent_id: str) -> None: ...
    async def run(self, agent_id: str, task: AgentTask) -> AgentResult: ...
    async def pause(self, agent_id: str) -> None: ...
    async def disable(self, agent_id: str) -> None: ...
    async def retire(self, agent_id: str) -> None: ...
```

#### 模块 7：Agent Protocol（Agent 间通信协议）

**职责**：定义 Agent 之间的标准化通信语义，基于 Core Message Bus 构建。

Agent Protocol 在 Message Bus 之上增加了一层语义：

```python
class AgentMessage(BaseModel):
    """Agent 间通信消息。"""
    id: str
    sender_id: str                    # 发送方 Agent ID
    target_id: str | None = None      # 接收方 Agent ID（None = 广播）
    conversation_id: str              # 对话/任务 ID（用于追踪）

    # 消息类型
    message_type: AgentMessageType

    # 消息内容
    payload: dict[str, Any]

    # 路由控制
    priority: int = 0
    ttl: int = 300                    # 消息过期时间（秒）
    reply_to: str | None = None       # 回复目标消息 ID

    # 审计
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentMessageType(str, Enum):
    """Agent 消息类型。"""
    # 任务委托
    DELEGATE = "delegate"             # 委托一个任务给另一个 Agent
    DELEGATE_RESULT = "delegate_result"  # 委托结果返回

    # 信息查询
    QUERY = "query"                   # 向另一个 Agent 查询信息
    QUERY_RESULT = "query_result"     # 查询结果返回

    # 通知
    NOTIFY = "notify"                 # 单向通知
    BROADCAST = "broadcast"           # 广播

    # 协调
    COORDINATE = "coordinate"         # 协作请求
    COORDINATE_ACK = "coordinate_ack" # 协作确认
```

#### 模块 8：Agent Context（Agent 上下文管理）

**职责**：管理 Agent 单次运行的上下文——接收到的输入、用到的工具、产出的结果。

```python
class AgentContext(BaseModel):
    """Agent 单次运行的上下文。"""
    agent_id: str
    session_id: str
    task: AgentTask

    # 运行时状态
    memory_snapshot: list[MemoryItem] = []   # 启动时加载的记忆快照
    tool_calls: list[ToolCall] = []          # 本次运行的工具调用记录
    messages: list[AgentMessage] = []        # Agent 间通信记录

    # 资源追踪
    token_usage: int = 0
    elapsed_ms: int = 0
    error: str | None = None

    # 控制
    abort_requested: bool = False


class AgentTask(BaseModel):
    """交给 Agent 执行的任务。"""
    task_id: str
    agent_id: str
    user_id: str

    # 任务内容
    instruction: str                  # 人类的自然语言指令
    input_data: dict[str, Any] = {}   # 结构化输入
    context: dict[str, Any] = {}      # 额外上下文

    # 约束
    max_tokens: int = 32000
    max_tool_calls: int = 50
    timeout: int = 120
    require_approval: bool = False
```

### 3.4 数据流

**核心流程：用户通过 Application 调用 Agent**

```
User (通过 Application)
    │
    ▼
1. Application 构造 AgentTask
    │
    ▼
2. Identity Manager 验证用户权限
    │
    ▼
3. Agent Scheduler 路由到目标 Agent
    │
    ▼
4. Agent Instance 启动运行
    │
    ├──→ Memory Layer: 按 Agent 的 MemoryProfile 加载记忆
    │     注入到 System Prompt
    │
    ├──→ [思考循环]
    │     Brain 决定 → 调用 Tool → 获得结果 → 继续思考
    │     │
    │     ├── 如果需要 → Agent Protocol 委托子任务给其他 Agent
    │     └── 如果完成 → 组装最终结果
    │
    ├──→ Memory Layer: 自动写入 Episodic Memory
    │
    ▼
5. 返回 AgentResult 给 Application
    │
    ▼
User 看到结果
```

**Agent 间协作流程：Orchestrator → Specialist**

```
Orchestrator Agent (协调者)
    │
    ├──→ [委托] 通过 Agent Protocol 发送 DELEGATE 消息
    │    │
    │    ▼
    │  Research Agent (专家)
    │    │  执行研究任务
    │    │  ├──→ 调 Knowledge Layer 查资料
    │    │  └──→ 调 Web Search Tool
    │    │
    │    └──→ [返回] DELEGATE_RESULT
    │
    ├──→ [委托] Analyst Agent (专家)
    │    │  分析研究结果
    │    │
    │    └──→ [返回] DELEGATE_RESULT
    │
    └──→ [整合] 生成最终报告
```

### 3.5 接口定义

#### 3.5.1 Agent Layer 包结构

```
agents/                              # 顶层包（与 core/ 同级）
├── __init__.py                      # 导出主要接口
├── identity.py                      # AgentIdentity / AgentRole / CapabilityDecl
├── permission.py                    # AgentPermission / AuditLevel
├── tools/
│   ├── __init__.py
│   ├── registry.py                  # ToolRegistry
│   └── protocol.py                  # Tool / ToolCall / ToolHandler
├── memory.py                        # MemoryProfile
├── lifecycle.py                     # AgentLifecycleManager / AgentLifecycleState
├── protocol.py                      # AgentMessage / AgentMessageType / AgentProtocol
├── context.py                       # AgentContext / AgentTask / AgentResult
└── config.py                        # AgentLayer 配置模型
```

#### 3.5.2 与 Core Layer 的关系

Agent Layer 依赖 Core Layer：
- `core.agent` → 底层 Agent 实例管理
- `core.bus` → 消息通信（Agent Protocol 构建于 Message Bus 之上）
- `core.identity` → 用户身份和权限检查
- `core.config` → Agent Layer 配置
- `core.logging` → 链路追踪

Agent Layer 依赖 Memory Layer：
- `core.memory` → 记忆读写（通过 MemoryProfile 控制）

Agent Layer **不直接依赖** Knowledge Layer（通过 Tool 间接调用）。

#### 3.5.3 角色预定义模板（组织约定）

以下角色预定义作为系统内置角色，用户可自定义扩展：

| 角色        | 默认能力                         | 默认工具                             | 默认记忆          | 行为模式           |
| ----------- | -------------------------------- | ------------------------------------ | ----------------- | ------------------ |
| ANALYST     | 数据分析、报告生成                 | knowledge_query, code_execute, file_save | Session + Episodic | 接收数据 → 分析 → 报告 |
| SECRETARY   | 日程管理、任务提醒                 | memory_read, notify_user             | Session + Semantic | 维护用户偏好和日程    |
| RESEARCHER  | 信息检索、资料整理                 | web_search, knowledge_query, memory_write | Session + Episodic + Semantic | 搜索 → 整理 → 摘要 |
| ASSISTANT   | 通用问答、任务执行                 | 所有基础工具                         | 三种全开           | 根据指令动态适配     |
| ORCHESTRATOR| 任务分解、Agent 编排              | agent_message（委托）               | Session + Semantic | 分解 → 委托 → 整合   |
| CRITIC      | 审核、纠错、质量检查               | memory_read, notify_user            | 只读 Episodic     | 审查 → 反馈         |

## 4. 可选方案

### 方案 A：身份和能力分离设计（选定方案）

Agent Identity 只声明"我是谁"，能力通过注册的 Tools + Memory Profile 动态确定。

**优点**：
- 松耦合：同一个身份可以绑定不同的工具组合
- 灵活：用户可以为标准 Analyst 角色添加自定义工具
- 可审计：工具调用有明确的归属和记录

**缺点**：
- Agent 的身份和能力之间没有编译时约束（但这是有意为之——AI Agent 的能力应该是动态的）

### 方案 B：Agent 类继承体系

设计一个 Agent 基类，AnalystAgent、SecretaryAgent 等都继承自它。

**优点**：
- OOP 天然直觉
- 编译时可以验证方法存在

**缺点**：
- 继承树僵化：如果一个 Agent 需要同时具有 Analyst 和 Researcher 的能力怎么办？
- 修改基类可能导致所有子类受影响
- Agent 的能力边界不应该由继承结构定义，而应该由运行时声明定义

**为什么不选**：Agent 的本质是 AI 驱动的，不是 OOP 驱动的。能力组合应该像"插件"一样灵活，而不是像"类继承"一样固化。

### 方案 C：完全动态（无身份声明）

Agent 不做事前身份声明，完全由运行时行为决定。

**优点**：
- 最大灵活性

**缺点**：
- 没有可发现性：系统不知道有哪些 Agent 可用
- 无法做权限控制
- 无法做 Agent 间的语义路由

**为什么不选**：身份声明是 Agent Layer 的"契约"，没有契约就没办法做管理、路由和权限控制。

## 5. 影响分析

| 维度       | 影响说明                                         |
| ---------- | ------------------------------------------------ |
| 性能       | Agent 启动时需加载 Memory + 初始化 Tools，延迟约 100-500ms；Tool 执行受外部 API 速度影响 |
| 安全       | 双层权限模型（Agent × User）提供安全边界；高风险 Tool 需用户确认 |
| 可维护性   | Agent 身份 / 能力 / 权限分离设计，任一维度可独立修改 |
| 向后兼容性 | 本层为新增设计，无兼容性问题；不影响 Core/Memory 层的已有定义 |
| 依赖变更   | 无新增外部依赖；Agent Protocol 基于已有 Message Bus 构建 |

## 6. 实施计划

### Phase 1.3a：Agent Layer 抽象层（当前 RFC 对应的实施步骤）

1. 创建 `agents/` 顶层包及目录骨架
2. 实现 `identity.py`：AgentIdentity / AgentRole / CapabilityDecl
3. 实现 `tools/` 子包：Tool 数据模型 + ToolRegistry 抽象
4. 实现 `permission.py`：AgentPermission 模型
5. 实现 `memory.py`：MemoryProfile 模型
6. 实现 `lifecycle.py`：AgentLifecycleManager 抽象 + 状态机
7. 实现 `protocol.py`：AgentMessage / AgentMessageType
8. 实现 `context.py`：AgentContext / AgentTask
9. 实现 `config.py`：Agent Layer 配置模型

### Phase 1.3b：Agent Protocol + Tool 执行器

1. 实现 Agent Protocol 的 Message Bus 绑定（发送/接收 AgentMessage）
2. 实现 ToolRegistry 的基础执行引擎
3. 编写集成测试：Agent 定义 → 注册 → 工具调用 → 记忆读写 → 生命周期流转

### 验收标准

- [ ] AgentIdentity 模型完整涵盖身份声明的所有维度
- [ ] AgentRole 预定义 8 种角色 + 支持自定义扩展
- [ ] ToolRegistry 支持注册 / 发现 / 执行完整流程
- [ ] AgentPermission 支持双层权限检查
- [ ] MemoryProfile 支持三种记忆类型的独立配置
- [ ] AgentLifecycleManager 支持完整生命周期状态机
- [ ] AgentMessage 支持 7 种消息类型
- [ ] 所有模块无循环导入

## 7. 相关文档

- [RFC-001: Core Layer Architecture](docs/rfc/001-core-layer-architecture.md)
- [RFC-002: Memory Layer Architecture](docs/rfc/002-memory-layer-architecture.md)
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- [ADR-005: Agent 身份模型](docs/adr/ADR-005-agent-identity-model.md)
