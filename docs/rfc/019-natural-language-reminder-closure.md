# RFC-019：自然语言提醒闭环

## 状态

Adopted

## 采纳记录

- 由 SP-009 实施。
- 通过 PR #19 合并。
- Approved Head：`42697e2787d9d9e33f4a7b40c3dd0ea092dcf742`。
- Merge Commit：`b1274d066cbc01053144cba8d5654a5f8c8a21da`。
- 采纳日期：`2026-07-16`。

## SP-014B 兼容性记录

- SP-014B 通过 PR #33 合并为 `22f85db16a43e7d09a903859a26ac6a310370d81`。
- 在显式包含 `上午/下午/晚上` 时，既有确定性解析器接受中文小时 `一` 至 `十二`，并继续支持既有 `半`、`一刻` 与阿拉伯数字分钟组合。
- 不带时段的中文小时，以及后天、星期、相对或模糊时间、中文分钟、二刻/三刻、Recurring Reminder 和 LLM 时间解析仍不受支持。
- 兼容性修复后 ACC-014 场景 K 通过；解析器架构和未来时间解析路线没有改变。

## 背景

SP-004 和 SP-005 引入了持久化的 UserTask、Reminder、Scheduler Job、JobRun 与 ReminderOccurrence，但面向用户的 CEO Assistant 路径尚不能创建或查询完整链路。SP-009 在不增加外部通知投递的前提下，提供首个可测试产品切片。

## 用户结果

一条受支持的中文提醒语句会创建一个 UserTask、一个 Reminder 和一个持久化 one-shot Scheduler Job。用户获得机器可读 ID，可通过 API 或 CLI 查询聚合状态；进程重启不会丢失状态，之后可观察到一个已触发或失败的 occurrence。

## 支持的语言子集

确定性解析器接受 `今天/明天` 加 `HH:MM`、`HH：MM` 或 `上午/下午/晚上 H 点`。当显式包含 `上午/下午/晚上` 时，`H` 可以是阿拉伯数字或 `一` 至 `十二`；不带时段的中文小时明确不受支持。解析器也会完整消费 `半`、`一刻` 与显式阿拉伯数字分钟。

下周、相对或模糊时间、中文分钟、重复日程、节假日或缺少时间的表达以 `reminder.time_unsupported` 失败；过去时间以 `reminder.time_in_past` 失败。LLM 输出不得决定时间。

## Task 与 Reminder 的区别

Task 截止时间与 Reminder 调度是不同概念。`添加任务：...` 等显式 Task 形式只创建 UserTask；若包含受支持时间，则将该时间以 UTC `due_at` 持久化，但不创建 Reminder 或 Scheduler Job。无法识别的 Task 时间会创建不带 `due_at` 的 Task，并报告时间未识别。显式 Reminder 标记必须具有受支持的未来 `due_at`，不得降级为仅创建 Task 的成功结果。

## 时间合同

`SystemSettings.timezone_name` 提供 IANA 解释时区，对应 `AI_LAB_TIMEZONE`，默认值为 `Asia/Shanghai`。`Clock.now()` 是带时区的 UTC 时刻。用户输入按配置时区解释，以 UTC 持久化，并与时区名称一起返回带时区的 ISO-8601 值。

## 编排所有权

组合根注入 `NaturalLanguageReminderOrchestrator`。CEO Assistant 解析意图后调用该服务，不直接访问 Repository，也不自行构造 Scheduler Job。编排器把 Reminder 与 Job 创建委托给既有 `ReminderSchedulerBridge`，保留 SP-005 的 Saga 与对账所有权。

## Saga 与补偿

三个 SQLite 数据库不被描述为单一事务。系统先创建 UserTask；Bridge 失败时，任何可恢复的 Reminder 失败保留在既有 Saga 中，同时把 UserTask metadata 标记为 `scheduling_status=failed`，响应为非成功 `FailureInfo`。之后以相同 idempotency key 重试时，复用确定性 UserTask 并对账匹配的 Reminder，不得伪造成功。

## 幂等性

API 接受 `Idempotency-Key` 或请求字段。两者都没有提供时，`/chat` 生成新的非空请求键，因此两个独立的无键请求会创建不同链路。系统只持久化 SHA-256 哈希，并从工作空间范围与该哈希派生稳定 UserTask ID。

相同显式键与规范化意图返回既有链路；相同键配合不同意图返回 `reminder.idempotency_conflict`。标题不做全局去重。

## 失败语义

- 不支持或缺少时间：`reminder.time_unsupported`。
- 过去时间：`reminder.time_in_past`。
- Reminder/Scheduler 禁用：在创建 UserTask 前返回 `reminder.unavailable`。
- Saga 调度失败：返回带可恢复 ID 的 `reminder.scheduling_failed`。
- 触发失败：持久化 occurrence 与 Scheduler 重试或最终失败，不得报告 `triggered`。

## 状态聚合

`ReminderStatusView` 读取持久化的 UserTask、Reminder、Scheduler Job 与最新 ReminderOccurrence。它公开 `scheduled`、`retrying`、`triggered`、`failed` 或 `cancelled`，以及稳定 ID、最新失败和可重试性。LLM 输出、日志、EventBus 与进程内存都不是真相源。

## API 与 CLI 可见性

- 自然语言创建：`POST /chat`。
- 聚合查询：`GET /reminders/{reminder_id}/status`。
- Occurrence：`GET /reminders/{reminder_id}/occurrences`。
- CLI：`python -m cli reminder-status <reminder_id>`。

所有生产路径都使用共享组合根以及准入和安全边界。

## 重启与有效单次执行

SQLite Reminder 与 Scheduler 持久化在启动时恢复已调度工作。既有唯一 occurrence key 与 one-shot 终态 Job 语义可防止在重复 tick、恢复和重启期间产生重复的成功 occurrence。

## 验收策略

集成测试使用公开 `/chat` 端点、真实 FastAPI lifespan、真实组合根、真实 SQLite Store、真实 Scheduler/Reminder Handler、显式 Mock Provider 与固定注入时钟。测试验证创建、幂等重试、重启、到期执行、单一 occurrence 与重启后状态；另一个注入 Handler 故障的场景验证重试和失败可见性。

## 已知限制

本 RFC 不包含外部通知、Inbox UI、Recurring Reminder、复杂日期语言、LLM 时间解析、用户时区 UI、分布式调度、多用户授权或 Web UI。可见结果仅存在于应用内查询状态。
