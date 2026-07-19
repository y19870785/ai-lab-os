# SP-014 Unified Inbox 手工验收

Status: PASSED / FINAL

Manual Product Acceptance = PASSED

## 验收基线

- SP-014：PR #32，Squash Commit `5bad5d412f9f2dabb158527a96c20c6e95e86d6e`
- SP-014B：PR #33，Squash Commit `22f85db16a43e7d09a903859a26ac6a310370d81`
- 合并后 main Quality Gate：run `29690136483`，Ruff SUCCESS，pytest (non-real) SUCCESS
- pytest：`1154 passed, 6 skipped, 27 warnings`
- Provider：隔离 mock；未配置或调用真实模型密钥
- Workspace：canonical default workspace，并包含显式跨 workspace 隔离验证
- 本地原始 Evidence 不提交 GitHub；本文件仅保留可审查的验收事实

## 最终场景状态

| 场景 | 结果 | 最终验证事实 |
|---|---|---|
| A — Capture | PASSED | CEO Assistant 明确 capture 创建一条 pending InboxItem，不创建 Task、Reminder 或 Work Log，确定性响应无 Mock/API Key 噪音 |
| B — List / Show | PASSED | CEO Assistant、CLI 与 API 读取同一 pending 状态；read 前后业务对象 ID 集合不变 |
| C — Resolve to UserTask | PASSED | 创建一个真实 UserTask，Inbox 记录目标 ID；重复解析稳定冲突且不重复创建；Daily Agenda 可见目标 |
| D — Resolve to Reminder | PASSED | 复用正式 Reminder orchestration 创建 backing UserTask、Reminder 与 Scheduler Job；重复解析不复制链路 |
| E — Resolve to Work Log | PASSED | 创建一个真实 Work Log，内容与来源 metadata 正确；重复解析不复制目标 |
| F — Note / Dismiss | PASSED | Note 以空目标完成解析；Dismiss 保留原记录且不创建外部目标 |
| G — Restart persistence | PASSED | 重启后 Inbox、claim、目标 ID、状态、revision 与解析关系保持；重复解析仍稳定冲突 |
| H — Workspace isolation | PASSED | 其他 workspace 无法 list/get/resolve/dismiss；不创建 claim 或目标对象 |
| I — Different-type race | PASSED | 独立容器竞争解析同一 Item 时只有 claim 类型可创建目标，无孤儿目标，失败方得到稳定 claim 冲突信息 |
| J — Same-type race / crash recovery | PASSED | 同类型竞争最多一个目标；从 `claimed` 与 `target_created` 中断点均可恢复并完成同一 Saga |
| K — Existing intent compatibility | PASSED | 中文小时 Reminder 输入及其余五条既有输入保持原 intent/effect 与副作用合同，不漂移到 Inbox |
| L — API security / error semantics | PASSED | Bearer auth、CORS allowlist、400/403/404/409、workspace 边界与 FailureInfo 脱敏合同全部通过 |

ACC-014：A～L 全部 PASSED，正式最终结论为 **PASSED / FINAL**。

## 场景 K 最终复验

核心输入：

```text
提醒我明天下午三点开会
```

最终结果：HTTP 200；现有 `task/write` 路由产生 `reminder/write` 业务结果，只创建一条 backing UserTask、Reminder 与 Scheduler Job 链，不创建 InboxItem；回答无 Mock 配置噪音；相同显式幂等键复用同一链路。

SP-014B 只扩展确定性 Reminder Parser：支持 `今天/明天 + 上午/下午/晚上 + 中文小时一至十二`，并继续复用阿拉伯数字、`HH:MM`、`半`、`一刻` 和数字分钟能力。中文小时无 period、后天、星期、相对/模糊时间、中文分钟、二刻/三刻、Recurring Reminder 与 LLM 时间解析仍不支持。

其余兼容输入最终保持：Work Log `work_log/write`、普通 Task `task/write`、今日提醒 `reminder_list/read`、今日日程 `daily_agenda/read`、普通聊天 `chat/chat`；均未漂移到 Unified Inbox。

## 验收过程说明

1. 场景 E 首次使用不存在的 `--content` 参数，命令以参数错误退出。该记录属于 `INVALID_ACCEPTANCE_COMMAND`，不是产品缺陷；改用正式 `--title / --description` 合同后场景通过。
2. 场景 K 在 SP-014 初次验收中暴露中文数字小时不兼容，返回 `reminder.time_unsupported`。SP-014B 在既有 parser 内完成最小修复并通过 PR #33 合入。
3. K/L 首次外部复验驱动使用大小写敏感方式读取 HTTP 响应头，误判 `WWW-Authenticate` 与 CORS header。修正仓库外驱动后，在全新数据目录中 K/L 均通过；未修改产品代码。

## 持久化 claim 验收结论

`inbox_resolution_claims` 已通过真实竞争与崩溃恢复验收：

- claim 必须在任何外部目标写入前取得；
- 不同解析类型只有 claim 赢家可调用目标 Service；
- 同类型竞争复用确定性 ID 或幂等键；
- `claimed` 与 `target_created` 均可由新 Service 实例恢复；
- Inbox 完成状态与 claim `completed` 最终一致；
- 错误 workspace 不得创建或修改 claim。

进程内锁仅是优化；持久化 claim 才是跨进程正确性边界。

## 保留边界

- 首次 PR #33 pytest attempt 中观察到 Scheduler 状态短暂为 `running` 的时序波动；唯一重跑后通过。该测试不涉及 SP-014B 修改文件，不作为 SP-014B 缺陷，也不在本任务修复。
- CI-002、QUALITY-001、Knowledge Layer 主链路、完整 Agent Runtime 产品闭环、多用户/Workspace 管理、外部通知和 Recurring Reminder 仍未完成。
- SP-015 为 `UNBLOCKED_FOR_PLANNING / NOT_STARTED`，未在本验收或治理任务中启动。
