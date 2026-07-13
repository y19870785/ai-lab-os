# ADR-022: Scheduler Pattern

**状态：** Accepted
**版本：** v0.21.0
**日期：** 2026-07-13

## 上下文

AI-Lab 需要支持定时任务调度。需要决定：是自建轻量 Scheduler，还是依赖外部调度系统（如 APScheduler、Celery）。

## 决策

**自建轻量 Scheduler Runtime**，理由：

1. **依赖方向控制**：外部库可能迫使 Scheduler 直接调用业务代码，违反分层原则。自建 Scheduler 只委托 Workflow Runtime。
2. **零外部依赖**：AI-Lab 当前不引入第三方框架，保持纯 Python 标准库 + Pydantic + SQLite。
3. **可演进**：Tick-loop 架构简单，后续可升级为事件驱动或多进程模式，不影响上层接口。

## 替代方案

1. **APScheduler**：功能丰富但引入外部依赖，且直接执行 Python 函数，不利于分层隔离。
2. **Celery**：重量级，需要 Redis/RabbitMQ，不适合当前阶段。

## 后果

- **正面**：轻量、可控、与 AI-Lab 分层完全一致。
- **负面**：缺少分布式调度能力（后续可扩展），Cron 解析只支持 `*/N` 格式。
