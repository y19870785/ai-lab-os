# RFC-020: Reminder Inbox and User-Friendly Local Access

## Status

Adopted

## Adoption Record

- Implemented by SP-010
- Merged via PR #21
- Approved Head: `2719793102b4318f4b98162f4b288710fe4b44f8`
- Merge Commit: `af437afc32dcb17da68d600d6840ec94c8cbe681`
- Adoption Date: `2026-07-16`

## Context

SP-009 提供了按 `reminder_id` 查询单条聚合状态的真实闭环，但用户无法在不知道 ID 的情况下查看自己的提醒。SP-010 增加持久化站内 Inbox，并保持 Reminder、Scheduler 与 UserTask 的既有所有权边界。

## User Outcome

用户可通过 `GET /reminders`、`python -m cli reminders` 或确定性中文查询查看提醒列表。列表支持聚合状态、今天/未来时间范围、稳定分页和 workspace 隔离；重启后仍从 SQLite 真相源重建。

## Query Contract

- 状态：`scheduled`、`retrying`、`triggered`、`failed`、`cancelled`；
- 时间：`today` 按 `SystemSettings.timezone_name` 的本地自然日计算，`upcoming` 从 `Clock.now()` 开始；
- 分页：`limit` 为 1–100，`offset` 非负，`count` 仅表示当前页数量，`has_more` 表示是否存在下一条匹配记录；
- 排序：`remind_at ASC, id ASC`，由 SQLite 固定；
- 状态聚合：复用 ADR-040，不创建第二套生命周期真相。

## Persistence And Bounded Aggregation

Reminder 与 UserTask 位于不同 SQLite 数据库，不伪装成跨库 JOIN。Repository 使用 `LIMIT/OFFSET` 分批读取 Reminder，Inbox 每批最多读取 100 条，并在找到当前页加一条后停止。UserTask 用于 workspace 校验，Scheduler Job 与最新 Occurrence 用于 ADR-040 聚合；不会把所有记录一次性加载到内存。

## Workspace Isolation

新建 Task 在 metadata 中记录规范化的 `tenant_id/workspace_id/namespace`。Inbox 只返回与请求 `WorkspaceKey` 完全一致的 Task。历史记录没有 workspace metadata 时只归入默认 workspace，不会对命名 workspace 可见。本轮不宣称已经建立用户身份、RBAC 或多租户安全系统。

## Natural-Language Queries

支持确定性查询：`查看我的提醒`、`查看提醒`、`查看待触发提醒`、`查看今天的提醒`、`查看已触发提醒`、`查看失败提醒`。这些查询不调用 LLM、不创建新 Task/Reminder/Job，结果 metadata 与 API 使用同一 Inbox Page 模型。

## Local UTF-8 Contract

API JSON 成功与失败响应显式声明 `application/json; charset=utf-8`，JSON 字节使用 UTF-8。PowerShell 验收优先按响应 charset 解码；CLI 的 `--json` 使用 `ensure_ascii=False` 输出中文。此契约不解决所有历史 Windows 终端代码页问题。

## Known Limitations

SP-010 不实现 Web UI、外部通知、Recurring Reminder、全文搜索、跨 workspace 管理视图、用户身份、RBAC、分布式查询或 Reminder Inbox 推送。跨 SQLite 聚合不是快照事务；深度稀疏过滤的成本可能随记录量增长。
