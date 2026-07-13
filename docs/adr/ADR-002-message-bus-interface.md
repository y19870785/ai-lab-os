# ADR-002: Message Bus 接口设计

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 002                                  |
| **标题**     | Message Bus 接口设计                   |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-001                              |
| **取代**     | —                                    |

## 1. 背景

Core Layer 需要模块间异步通信能力。消息系统是解耦关键：Config 更新通知、Agent 任务分发、事件驱动的 Knowledge Layer 索引——都需要一个统一的异步通信机制。

## 2. 决策

采用**双模式消息总线**，通过单一抽象提供两种通信模式：

### 模式 1：Event Bus（发布/订阅）

- 一对多：一个事件 → 多个订阅者
- 典型场景：配置变更通知 (`config.updated`)、任务完成通知 (`agent.completed`)
- 接口：`publish(topic, event)` + `subscribe(topic, handler)`

### 模式 2：Task Queue（点对点任务分发）

- 一对一：一个任务 → 一个消费者
- 典型场景：Agent 执行请求、异步索引任务
- 接口：`send(queue, task)` + `register_worker(queue, worker)`

### Phase 1 实现选择：内存通道（`asyncio.Queue`）

- 无外部依赖，单进程即可工作
- 适合开发、测试和单机部署
- Phase 2 迁移到 Redis Pub-Sub / 任务队列时，只替换 `bus/` 下的具体实现

### 事件/任务数据模型

```python
class Event(BaseModel):
    id: str                    # UUID4
    topic: str                 # "agent.started"
    source: str                # 产生模块名
    timestamp: datetime
    payload: dict[str, Any]

class Task(BaseModel):
    id: str                    # UUID4
    queue: str                 # "agent.run"
    payload: dict[str, Any]
    priority: int = 0
    max_retries: int = 3
    timeout: int = 60
```

## 3. 后果

### 正面

- 单一抽象降低学习成本，Event Bus 和 Task Queue 使用同一套 MessageBus 接口
- Event/Task 数据模型统一，便于链路追踪
- 内存实现零依赖，上手即可用
- 接口设计预留了分布式扩展点（topic → channel，queue → 消息队列）

### 负面

- Event Bus 和 Task Queue 共用接口，部分参数对特定模式无意义（如 Event 不需要 `max_retries`）
- 内存实现不支持进程间通信，多进程部署需要 Phase 2 换实现

### 风险

- 从内存切换到 Redis/RabbitMQ 时，Topic/Queue 的语义映射需要仔细设计
- 内存模式下事件丢失风险（进程崩溃后未消费的事件丢失）

## 4. 理由

为什么不分别设计 Event Bus 和 Task Queue 两个独立接口？

1. **统一性**：两者底层都是"发布+投递"语义，拆成两套接口增加重复
2. **使用便利**：调用方只需要 `from core.bus import message_bus`，不需要区分要用哪个 Bus
3. **扩展灵活**：未来可以在 MessageBus 实现中根据 Topic/Queue 自动路由到不同的后端

为什么不直接上 RabbitMQ / Redis Streams？

- **YAGNI**：单进程开发阶段不需要分布式消息队列
- **降低初始复杂度**：从简单开始，需要时再换
- **测试友好**：内存实现便于单元测试（无需启动外部服务）

## 5. 相关链接

- [RFC-001 §3.3 模块 3](docs/rfc/001-core-layer-architecture.md#33-模块说明)
- [ADR-001: Core Layer 包结构](docs/adr/ADR-001-core-layer-package-structure.md)
