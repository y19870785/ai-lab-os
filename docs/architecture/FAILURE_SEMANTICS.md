# AI-Lab 失败语义与可观测性

> SP-002 状态：Implemented on branch / Awaiting review

本文定义 AI-Lab 运行时表达失败的唯一公共契约。实现位于 `core/errors/`，Agent、Task、Scheduler、System Health 和 API 不得再各自维护同义错误模型。

## 统一模型

`ErrorCategory` 包含：`VALIDATION`、`NOT_FOUND`、`ALREADY_EXISTS`、`NOT_CONFIGURED`、`DISABLED`、`UNAVAILABLE`、`TIMEOUT`、`CANCELLED`、`CONFLICT`、`DEPENDENCY_FAILURE`、`EXECUTION_FAILURE`、`PERSISTENCE_FAILURE`、`PERMISSION_DENIED`、`RATE_LIMITED`、`INTERNAL`。

`RuntimeStatus` 包含：`OK`、`DEGRADED`、`FAILED`、`DISABLED`、`NOT_CONFIGURED`、`NOT_INITIALIZED`、`STARTING`、`STOPPING`、`STOPPED`。Health 输出中 `OK` 序列化为 `healthy`，用于保持现有健康检查语义。

`FailureInfo` 是不可变且可序列化的失败对象，字段如下：

```text
code, category, message, component, operation,
retryable, severity, trace_id, cause_type, details
```

消息和详情在构造时执行敏感信息脱敏。完整堆栈只进入日志，不进入 `FailureInfo`、事件或 API。

## 异常与结果

- 构造失败、必需配置缺失、注册冲突、非法生命周期和系统无法 ready 必须抛出异常。
- Agent、Task、Job 等预期执行失败可返回结构化失败 Result，但状态不得为成功，并必须携带 `FailureInfo`。
- 未知异常必须使用 `logger.exception()` 保留堆栈，再转换为 `INTERNAL`。
- 显式关闭的服务使用 `DISABLED`，应启用但缺少配置的服务使用 `NOT_CONFIGURED`。
- 错误文本不得放入 `answer` 或成功 `result` 字段。

`retryable=True` 只表示调用方可以根据策略重试，不表示运行时已经自动重试。超时、短暂不可用和部分依赖故障通常可重试；校验错误、权限错误、冲突和缺少配置默认不可重试。

## Agent

Agent 失败返回 `status=failed`、空 `answer` 和结构化 `failure`，Runtime 生命周期从 `RUNNING` 进入 `ERROR`。主要错误码包括：

```text
agent.memory.retrieve_failed
agent.knowledge.retrieve_failed
agent.provider.generate_failed
agent.tool.execute_failed
agent.memory.save_failed
```

LLM 已成功回答但 Memory 保存失败时，回答保留，状态为 `degraded`，生命周期进入 `DEGRADED`，并明确告知调用方记忆没有可靠写入。

请求级能力开关是强契约：当请求启用 Memory、Knowledge 或 Tool 时，对应 Manager、Registry 或 Executor 必须已经配置；否则返回 `failed + FailureInfo`。只有请求显式将对应开关设为 `false` 时才允许跳过。

## Task

每个 Workflow 使用独立 attempt 循环。`max_retries=N` 表示首次执行后最多再重试 N 次。Retry 事件记录当前 `attempt`、`next_attempt` 和 `max_attempts`。达到上限后立即 fail-fast，不继续后续 Workflow。

空计划默认返回 `task.plan.empty`；完成态的 `errors` 必须为空；失败或超时态必须携带 `FailureInfo`。Checkpoint 只在 Workflow 真正完成后推进索引，因此不会跳过失败步骤或重复已完成步骤。

## Scheduler

Scheduler 保存最近 tick 时间、最近成功 tick、最近失败、连续失败数和后台 Job task 集合。成功 tick 清零连续失败；失败达到配置阈值后进入 `failed`，阈值前进入 `degraded`。

后台 task 必须被持有、观察异常并在 shutdown 时等待或取消。关闭顺序为停止 tick、阻止新任务、收集后台任务、发布关闭事件、关闭 Persistence。

## API

统一错误响应：

```json
{
  "status": "error",
  "code": "provider.timeout",
  "message": "Provider timed out",
  "component": "provider",
  "retryable": true,
  "trace_id": "...",
  "details": {}
}
```

HTTP 映射：校验 `400`，未找到 `404`，冲突或已存在 `409`，权限 `403`，未配置、禁用、不可用 `503`，超时 `504`，限流 `429`，内部错误 `500`。未知异常返回通用消息，不暴露路径、堆栈或内部详情。

CEO Assistant 或其他 Application 返回 `error`、`failed`、`not_configured`、`disabled` 时，ApplicationRuntime 必须转换为统一失败异常，由 API 中间件输出非 2xx 响应。错误文本不得放入 `answer`，原始内部异常不得进入客户端响应。

## Health 聚合

`SystemContainer.health()` 输出顶层状态和 `components`。EventBus、Provider、Memory、Application、Agent、Workflow 是必需服务；Knowledge 和 Scheduler 是否必需由 `SystemSettings` 决定。可选服务为 `disabled` 时不降低顶层状态；必需服务失败时顶层为 `failed`；可运行但存在非致命故障时为 `degraded`。

Provider Health 基于初始化状态，不在每次检查时调用外部网络。Memory Health 包含 Store 数量和最近已知失败；Store 成功操作或显式健康探针通过后会清除临时失败。Scheduler Health 包含 tick 与后台 Job 的实际运行信息。

关键组件的 `stopped`、`not_initialized`、`not_configured`、`disabled` 和 `failed` 都表示系统未就绪，顶层状态必须为 `failed`；关键组件 `degraded` 时顶层为 `degraded`。仅显式配置为可选的组件处于 `disabled` 时，才不会降低顶层状态。

## 失败事件

本轮触及的 Agent、Task、Scheduler 失败事件使用扁平 envelope：

```text
status, code, category, message, component, operation,
retryable, severity, trace_id, cause_type, details
```

trace id 同时进入事件 payload 和 metadata。不得只发布自由文本 `error`。

## 强制原则

**No Fake Success**：依赖失败、空计划或执行失败不得返回成功、Echo 或空实现结果。

**No Silent Failure**：后台异常必须进入日志、结构化状态和事件；禁止 `except Exception: pass`。

## 当前边界

SP-002 不处理 Knowledge Reindex、Chunk 持久化、DatabaseManager 连接所有权、Reminder 闭环、自动 Tool Calling 或 Coordination 扩展。Memory 最近失败状态当前由统一入口和主运行链路记录，更完整的 Store 级健康探针留待后续独立任务。
