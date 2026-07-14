# AI-Lab 系统组合架构

## 唯一入口

AI-Lab 的唯一 Composition Root 位于 `core/system/factory.py`：

```python
settings = load_system_settings()
system = await create_system(settings)
await system.start()
try:
    ...
finally:
    await system.shutdown()
```

SP-001 已通过 PR #1 合并到 `main`。`core.system.create_system()` 现为主分支唯一且权威的系统组合入口。Merge Commit：`0a36e250ab8382af6cf3ab3068e432aa69ba3399`。

`core/bootstrap.py` 仅是兼容包装器，不再保存另一套组装逻辑。

## SystemContainer

`core/system/container.py` 明确持有单进程内唯一的 EventBus、DatabaseManager、ProviderRegistry、ProviderFactory、LLM Provider、MemoryManager、KnowledgeManager、ToolRegistry、ToolExecutor、AgentRuntime、WorkflowRuntime、SchedulerRuntime、TaskRuntime、CoordinationRuntime、ApplicationRegistry、ApplicationRuntime 和 CEOAssistant。

## 生命周期

启动顺序：

```text
EventBus → Providers → Memory Stores → Knowledge → Tools
→ Agent → Workflow → Scheduler → Task → Coordination → Applications
```

关闭顺序与启动顺序相反。`start()` 与 `shutdown()` 均幂等；启动中途失败时，容器会清理已经启动的资源并抛出 `SystemInitializationError`。单个组件清理失败会记录日志，但不会阻止其他资源关闭。

## 入口接入

- CLI 交互模式在进程内创建一个 SystemContainer，并在退出时关闭。
- CLI 单次命令通过 `cli/runtime.py` 使用同一 Factory。
- FastAPI lifespan 创建并持有一个 SystemContainer，保存在 `app.state.system`。
- API dependency 只读取 lifespan 容器，不创建 Runtime。
- ApplicationRuntime 只派发到 ApplicationRegistry 中已注册的真实实例。

## Provider 模式

- `real`：必须配置 API Key、Base URL 和 Model，初始化失败直接失败。
- `mock`：仅在显式设置 `AI_LAB_PROVIDER_MODE=mock` 时允许。
- `test`：仅供隔离测试使用，数据目录必须由测试注入。
- `invalid`：配置缺失或不完整，系统拒绝启动。

优先级固定为：显式构造参数 > `AI_LAB_*` 环境变量 > `OPENAI_*` 兼容变量 > Provider 默认值。

## 默认禁用服务

Knowledge、Scheduler、Coordination 当前默认 `disabled`，必须通过设置显式启用。禁用状态会出现在健康检查中，不会伪装为 `healthy`。

## No Fake Success

以下行为已从主链路移除：

- 未注册 Application 自动创建；
- ApplicationRuntime 直接创建 OpenAI Provider；
- 真实调用失败后返回 Mock Echo；
- Agent 缺少 LLM 时返回成功 Echo；
- Task 或 Scheduler 缺少 WorkflowRuntime 时返回成功。

## 当前限制

- Episodic、Semantic、Decision SQLite Store 已由统一 `DatabaseManager` 管理共享连接所有权；Knowledge SQLite Store 与 SchedulerPersistence 尚未迁移。
- UserTask 尚未接入 Scheduler，Reminder 闭环未完成。
- Knowledge Chunk 持久化、Keyword Index 重建、Reindex 和 Citation 尚未完成。
- Agent 自动 Tool Calling 闭环尚未完成。
- Task Retry 循环问题未在 SP-001 中全面处理。
- Coordination 默认禁用，尚未接回 CEO Assistant 主链路。
- API 的通用 Task/Workflow 示例路由仍是 Prototype，不属于本次 `/work-logs` 验收范围。

## 禁止规则

除 `core/system/factory.py`、明确 Factory 和测试 Fixture 外，CLI、API Route、ApplicationRuntime 与业务 Application 不得实例化核心运行服务。
