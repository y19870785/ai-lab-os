# RFC-001: Core Layer Architecture

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **RFC 编号** | 001                                  |
| **标题**     | Core Layer 架构设计                    |
| **状态**     | 草稿                                  |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 ADR** | ADR-001, ADR-002                     |

## 1. 背景

AI-Lab 采用四层架构（Core → Knowledge → Agent → Application），Core Layer 作为最底层基础设施，上层所有模块都依赖其提供的通用能力。

当前 Foundation v0.1 已完成：
- 项目骨架与目录结构
- Python 项目初始化（pyproject.toml、requirements.txt）
- 基础配置管理（`core/config.py`，Pydantic 分层配置）
- 结构化日志（`core/logging.py`，JSON 格式输出）
- 顶层架构文档与开发指南

**尚未完成的 Core Layer 核心模块：**

- **消息系统（Message Bus）**：模块间异步通信，支持事件驱动
- **数据接口（Data Interface）**：统一的数据访问层（数据库、外部 API、缓存）
- **Agent 管理（Agent Management）**：Agent 注册、生命周期、调度
- **用户身份管理（Identity & Session）**：用户认证与会话管理

Phase 1.1 的目标是完成 Core Layer 的完整架构设计，明确各模块的职责边界、接口协议和协作方式，为后续实现提供蓝图。

## 2. 目标

- 定义 Core Layer 各子模块的职责边界和依赖关系
- 设计模块间通信协议（同步 API + 异步消息）
- 设计统一的数据访问层抽象
- 明确 Agent 管理的基础模型和生命周期
- **不在此次范围**：具体业务功能、Knowledge/Agent/Application Layer 的实现

## 3. 设计方案

### 3.1 整体思路

Core Layer 采用 **微内核 + 插件化** 的设计哲学：
- 内核最小化：只包含所有上层都依赖的绝对基础设施
- 通过接口（Protocol/ABC）定义扩展点，具体实现可替换
- 模块间通过 **Message Bus** 解耦，避免直接依赖
- 配置驱动一切：所有行为由配置层控制，不硬编码

### 3.2 模块架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Core Layer                           │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │  Config   │  │  Logging │  │    Message Bus       │  │
│  │  Manager  │  │  System  │  │  (事件总线/任务队列)    │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       │              │                   │              │
│  ┌────┴──────────────┴───────────────────┴──────────┐   │
│  │               Service Registry                   │   │
│  │            (服务注册/发现/健康检查)                 │   │
│  └────────────────────┬────────────────────────────┘   │
│                       │                                  │
│  ┌────────────────────┼────────────────────────────┐   │
│  │         Data Access Layer                       │   │
│  │  ┌─────────┐ ┌────────────┐ ┌────────────────┐ │   │
│  │  │ DB/ORM  │ │ Cache(Mem) │ │ External API   │ │   │
│  │  └─────────┘ └────────────┘ └────────────────┘ │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  ┌────────────────────────────────────────────────┐   │
│  │         Agent Runtime                          │   │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────────┐ │   │
│  │  │ Registry │ │ Lifecycle  │ │  Scheduler   │ │   │
│  │  └──────────┘ └────────────┘ └──────────────┘ │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  ┌────────────────────────────────────────────────┐   │
│  │         Identity & Session                     │   │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────────┐ │   │
│  │  │ AuthN    │ │ AuthZ      │ │ Session Mgr  │ │   │
│  │  └──────────┘ └────────────┘ └──────────────┘ │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.3 模块说明

#### 模块 1：Config Manager（已有，需增强）

**职责**：分层配置管理，提供全局统一的配置访问入口。

已有实现：
- Pydantic BaseModel 驱动，类型安全
- 三层覆盖：默认值 → YAML 文件 → 环境变量
- 全局单例 `config: Config`

**Phase 1.1 增强项**：

| 增强点         | 说明                                   |
| -------------- | -------------------------------------- |
| 配置热加载     | 支持运行时配置刷新（Signal / 文件 Watch） |
| 配置源抽象     | 支持从 Consul/etcd/DB 等远程源加载       |
| 配置校验 Schema | 使用 Pydantic 的 schema 做启动时验证     |

#### 模块 2：Logging System（已有，需增强）

**职责**：结构化日志，支持分级输出和链路追踪。

已有实现：
- JSON 格式化，控制台 + 文件双输出
- `get_logger(name)` 获取命名 logger

**Phase 1.1 增强项**：

| 增强点         | 说明                                    |
| -------------- | --------------------------------------- |
| 链路追踪 ID   | 每次请求/任务生成唯一 Trace ID，贯穿所有日志 |
| 异步日志写入   | 高性能场景下异步写入避免阻塞               |
| 日志级别动态调整 | 运行时通过 API 调整模块级别              |

#### 模块 3：Message Bus（新增）

**职责**：提供模块间的异步通信能力，解耦生产者和消费者。

**设计原则**：
- 不依赖特定消息队列实现（RabbitMQ / Redis Pub-Sub / 内存通道均可）
- 支持两种模式：Event Bus（发布/订阅）和 Task Queue（点对点任务分发）
- 通过抽象 `MessageBus` 协议定义接口，实现可替换

**核心接口**：

```python
class MessageBus(ABC):
    """消息总线抽象。"""

    @abstractmethod
    async def publish(self, topic: str, event: Event) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: EventHandler) -> Subscription: ...

    @abstractmethod
    async def send(self, queue: str, task: Task) -> str: ...   # 返回 task_id

    @abstractmethod
    async def register_worker(self, queue: str, worker: TaskWorker) -> None: ...
```

**Event 和 Task 的数据模型**：

```python
class Event(BaseModel):
    id: str           # UUID
    topic: str        # "agent.started" / "knowledge.updated"
    source: str       # 产生事件的模块名
    timestamp: datetime
    payload: dict[str, Any]

class Task(BaseModel):
    id: str           # UUID
    queue: str        # "agent.run" / "knowledge.index"
    payload: dict[str, Any]
    priority: int = 0
    max_retries: int = 3
    timeout: int = 60
```

**内置实现优先级**：
1. Phase 1：内存通道（`asyncio.Queue`），适合单进程开发
2. Phase 2：Redis Pub-Sub / 任务队列，适合生产部署

#### 模块 4：Data Access Layer（新增）

**职责**：提供统一的数据访问抽象，封装数据库 ORM、缓存、外部 API 调用。

**设计原则**：
- 不暴露具体 ORM/客户端实现（SQLAlchemy / Redis 等）
- 仓储模式（Repository Pattern）封装数据库操作
- 缓存穿透保护：先查缓存 → 查 DB → 回填缓存

**核心抽象**：

```python
class Repository[T](ABC):
    """泛型仓储接口。"""
    @abstractmethod
    async def get(self, id: str) -> T | None: ...
    @abstractmethod
    async def save(self, entity: T) -> T: ...
    @abstractmethod
    async def delete(self, id: str) -> bool: ...
    @abstractmethod
    async def query(self, spec: QuerySpec) -> list[T]: ...

class Cache(ABC):
    """缓存抽象。"""
    @abstractmethod
    async def get(self, key: str) -> Any | None: ...
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    @abstractmethod
    async def delete(self, key: str) -> bool: ...

class ExternalAPIClient(ABC):
    """外部 API 客户端抽象。支持重试、限流、熔断。"""
    @abstractmethod
    async def request(self, spec: APIRequest) -> APIResponse: ...
```

#### 模块 5：Agent Runtime（新增）

**职责**：Agent 的注册、生命周期管理和调度执行。

**核心概念模型**：

```python
class AgentSpec(BaseModel):
    """Agent 定义规范。"""
    name: str
    version: str
    description: str = ""
    capabilities: list[str] = []       # 能力标签，用于路由
    config_schema: dict[str, Any] = {}  # JSON Schema
    timeout: int = 60

class AgentInstance(BaseModel):
    """Agent 运行时实例。"""
    id: str           # UUID
    spec: AgentSpec
    status: AgentStatus  # created / running / paused / stopped / error
    created_at: datetime
    last_heartbeat: datetime | None = None
    metadata: dict[str, Any] = {}

class AgentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
```

**核心接口**：

```python
class AgentRuntime(ABC):
    """Agent 运行时管理。"""

    @abstractmethod
    async def register(self, spec: AgentSpec) -> str: ...  # 返回 agent_id

    @abstractmethod
    async def unregister(self, agent_id: str) -> None: ...

    @abstractmethod
    async def start(self, agent_id: str) -> None: ...

    @abstractmethod
    async def stop(self, agent_id: str) -> None: ...

    @abstractmethod
    async def get_status(self, agent_id: str) -> AgentStatus: ...

    @abstractmethod
    async def list_agents(self, filter: AgentFilter | None = None) -> list[AgentInstance]: ...
```

#### 模块 6：Identity & Session（新增）

**职责**：用户认证、授权和会话管理。

**设计原则**：
- API Key + JWT 双模式认证
- 简单的 RBAC（Role-Based Access Control）
- 会话支持持久化（Redis）和过期自动清理

**核心接口**：

```python
class IdentityManager(ABC):
    @abstractmethod
    async def authenticate(self, credentials: Credentials) -> Session | None: ...
    @abstractmethod
    async def authorize(self, user_id: str, action: str, resource: str) -> bool: ...
    @abstractmethod
    async def create_session(self, user_id: str) -> Session: ...
    @abstractmethod
    async def validate_session(self, token: str) -> Session | None: ...
    @abstractmethod
    async def revoke_session(self, token: str) -> None: ...
```

### 3.4 数据流

**典型流程：Agent 执行一个任务**

```
User/System
    │
    ▼
Identity Manager ──── 认证/授权
    │
    ▼
Agent Runtime ──── 查找空闲 Agent 实例
    │
    ├──→ Message Bus.send(task) ──→ Worker 消费
    │                                      │
    │    ┌──────────────────────────────────┤
    │    │            │                     │
    │    ▼            ▼                     ▼
    │  Config     Data Access           External API
    │  Manager    Layer                 Client
    │    │            │                     │
    │    ▼            ▼                     ▼
    │  Logging ──── 全链路 Trace ID
    │
    ▼
Message Bus.publish("agent.completed", event)
    │
    ▼
订阅者 (Knowledge Layer / Application Layer 等)
```

### 3.5 接口定义

#### 3.5.1 模块间依赖图

```
Identity & Session  →  Data Access Layer (用户/角色数据)
                     →  Config Manager (JWT secret 等配置)

Agent Runtime      →  Data Access Layer (Agent 状态持久化)
                   →  Message Bus (任务分发)
                   →  Logging System (链路追踪)

Message Bus        →  Config Manager (队列连接配置)
                   →  Logging System

Data Access Layer  →  Config Manager (连接串配置)
                   →  Logging System
```

#### 3.5.2 包结构

```
core/
├── __init__.py
├── config.py          # Config Manager（已有，增强）
├── logging.py         # Logging System（已有，增强）
├── bus/
│   ├── __init__.py
│   ├── protocol.py    # MessageBus 抽象协议
│   ├── event.py       # Event / Task 数据模型
│   └── memory.py      # 内存通道实现
├── data/
│   ├── __init__.py
│   ├── protocol.py    # Repository / Cache / API 抽象
│   ├── repository.py  # 仓储基类
│   ├── cache.py       # 缓存基类
│   └── client.py      # 外部 API 客户端基类
├── agent/
│   ├── __init__.py
│   ├── protocol.py    # AgentRuntime 抽象
│   ├── models.py      # AgentSpec / AgentInstance
│   └── runtime.py     # 默认运行时实现
└── identity/
    ├── __init__.py
    ├── protocol.py    # IdentityManager 抽象
    ├── models.py      # User / Session / Credentials
    └── manager.py     # 默认身份管理器实现
```

## 4. 可选方案

### 方案 A：模块全部内聚在 core/ 单层（选定方案）

**优点**：
- 简单直接，开发初期迭代快
- 所有基础设施在一个包内，导入方便
- 适合单进程部署场景

**缺点**：
- 如果 Core Layer 过大，后期拆分成本高

**选型理由**：当前阶段项目刚起步，追求简单可工作 > 过度抽象。

### 方案 B：拆分为 core/ 和 lib/ 两层

**优点**：
- lib/ 放真正与业务无关的通用库（如 Message Bus 实现）
- core/ 只放 AI-Lab 特有的基础设施

**缺点**：
- 当前阶段拆分过早，大部分模块边界还不确定
- 增加导入复杂度

### 方案 C：直接用第三方框架（Celery + FastAPI + SQLAlchemy）

**优点**：
- 开箱即用，不用自己造轮子

**缺点**：
- 框架耦合太重，后续替换成本高
- 不符合 Personal AI OS 的"轻内核"理念

**选型理由**：我们需要的是高度可控的基础设施，而不是被框架限制。会复用成熟库（如 SQLAlchemy），但通过抽象层保持替换性。

## 5. 影响分析

| 维度       | 影响说明                                         |
| ---------- | ------------------------------------------------ |
| 性能       | 消息总线内存模式无额外开销；Data Layer 加缓存层提高读性能 |
| 安全       | Identity 模块提供认证/授权，外部 API Client 支持限流熔断  |
| 可维护性   | 模块间通过接口和消息解耦，任一模块可独立替换           |
| 向后兼容性 | 新模块新增不破坏已有接口；Config/Logging 增强保持向下兼容 |
| 依赖变更   | 无新增外部依赖（Phase 1 内存实现）；Phase 2 可能引入 Redis |

## 6. 实施计划

### Phase 1.1a：基础抽象层（当前 RFC 对应的实施步骤）

1. 增强 Config Manager：配置热加载、Schema 校验
2. 增强 Logging System：Trace ID 贯穿
3. 创建 Message Bus 抽象 + 内存实现
4. 创建 Data Access Layer 抽象
5. 创建 Agent Runtime 抽象 + 基础实现
6. 创建 Identity & Session 抽象 + 基础实现

### Phase 1.1b：Core Layer 测试与集成

1. 模块单元测试覆盖
2. 集成测试：Config → Logging → Bus → Data → Agent 完整链路
3. 编写 ADR 记录关键决策

### 验收标准

- [ ] 所有 Core Layer 模块抽象定义完成（Protocol/ABC）
- [ ] Message Bus 支持 Event Pub-Sub + Task Queue 两种模式
- [ ] Data Access Layer 提供 Repository / Cache / API 三种抽象
- [ ] Agent Runtime 支持注册、启动、停止、查询状态
- [ ] Identity Manager 支持 API Key 认证 + Session 管理
- [ ] 所有模块有单元测试覆盖核心路径
- [ ] 不存在循环导入

## 7. 相关文档

- [架构文档](docs/architecture/ARCHITECTURE.md)
- [开发指南](docs/guides/DEVELOPMENT_GUIDE.md)
- [RFC-000: RFC 模板](docs/rfc/000-template.md)
- [ADR-001: Core Layer 包结构](docs/adr/ADR-001-core-layer-package-structure.md)
- [ADR-002: Message Bus 接口设计](docs/adr/ADR-002-message-bus-interface.md)
