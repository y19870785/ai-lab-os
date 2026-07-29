# ADR-039：自然语言 Reminder 编排边界

## 状态

Accepted

## 验收记录

- 由 SP-009 Accepted；
- PR：#19；
- Merge Commit：`b1274d066cbc01053144cba8d5654a5f8c8a21da`；
- Accepted Date：`2026-07-16`。

## 背景

自然语言创建 Reminder 跨越 UserTask、Reminder 与 Scheduler 持久化。若 CEO Assistant
直接调用 Repository 或 Scheduler，会复制 SP-005 Saga 行为，并使部分失败不可见。

## 决策

组合根创建一个 `NaturalLanguageReminderOrchestrator` 并注入 CEO Assistant。确定性
Parser 分别生成 Task/Reminder intent 与可选的 aware UTC `due_at`。Task 可以拥有
`due_at` 而不创建 Reminder；Reminder intent 必须包含受支持的未来 `due_at`。随后
Orchestrator 创建或复用 UserTask，并将 Reminder 与 Scheduler Job 创建委托给
`ReminderSchedulerBridge`。

注入 `Clock` 与配置的 IANA timezone。生产使用 `SystemClock`，测试使用显式可变 Clock。
显式 idempotency key 保留重试语义；`/chat` 在请求未提供 key 时为每个请求生成新的非空
key。只持久化 key hash，不保存原值。Bridge failure 以 `FailureInfo` 返回并记录到
UserTask metadata，既有 Reminder Saga 仍是恢复权威。

## 后果

- CEO Assistant 不拥有持久化细节或 Scheduler Job 构造；
- Reminder/Scheduler 禁用时仍可处理仅 Task 输入；
- 编排不可用时，Reminder 输入在创建 Task 前失败；
- 跨数据库行为仍是可恢复 Saga，不虚构事务；
- 支持的自然语言子集有意保持小而确定。

## 拒绝的替代方案

- LLM 推导时间：不确定且难测试；
- CEO Assistant 直接调用 Repository：重复所有权；
- 全局标题去重：阻止合法的同标题 Reminder；
- 静默回退到仅 Task：制造虚假成功。
