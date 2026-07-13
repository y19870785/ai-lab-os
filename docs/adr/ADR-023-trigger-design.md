# ADR-023: Trigger Design

**状态：** Accepted
**版本：** v0.21.0
**日期：** 2026-07-13

## 上下文

Scheduler 需要支持多种触发方式。需要考虑：每种 Trigger 的计算逻辑、验证规则、是否可以组合。

## 决策

**五种独立 Trigger 类型，不组合**：

| 类型 | 说明 | 触发条件 |
|------|------|---------|
| CRON | Cron 表达式 | `now >= next_run_at`，`next_run_at` 由 Cron 表达式计算 |
| INTERVAL | 固定间隔 | `now >= next_run_at`，`next_run_at = now + interval` |
| ONE_SHOT | 一次性 | `now >= run_at`，触发后 `next_run_at = None` |
| MANUAL | 手动触发 | 不自动触发，仅通过 API 调用 |
| EVENT | 事件触发（预留） | 由 EventBus 事件驱动 |

**不应该组合 Trigger**（如 "Cron AND Interval"），因为这会引入复杂的优先级和冲突解决逻辑。如果需要复杂调度，应在 Workflow 层编排，而非 Trigger 层。

## TriggerEngine 设计

- `should_fire(trigger, now) → bool`：纯函数，判断是否触发
- `compute_next(trigger, now) → datetime | None`：计算下次触发时间
- `validate(trigger) → bool`：验证 Trigger 配置

## Cron 策略

当前版本仅支持 `*/N` 格式（如 `*/5 * * * *` 每 5 分钟）。完整的 Cron 解析器（支持具体值、范围、列表）作为 v0.22.0 的改进项。

## 后果

- **正面**：简单、可测试、五种类型覆盖绝大多数场景。
- **负面**：Cron 支持有限；不支持组合 Trigger。
