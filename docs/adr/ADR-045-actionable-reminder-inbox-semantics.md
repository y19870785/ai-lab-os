# ADR-045：可行动 Reminder Inbox 语义

**Status:** Accepted
**Date:** 2026-07-17

## 验收记录

- Accepted through SP-011
- PR #23
- Approved Head: `beb99115dd273a9fe55e86d21e65f714e7f7f52f`
- Merge Commit: `5c4b442b2b5c7f934ac381020ba8b310976d5d3a`
- Accepted Date: 2026-07-17

## 背景

既有 `upcoming` 过滤仅表示 `scheduled_for >= now`。它适用于历史与诊断组合，但可能包含未来已取消提醒，因此不能回答“接下来需要关注什么”这一产品问题。

## 决策

Add the explicit `pending` inbox view:

```text
status in (scheduled, retrying)
and scheduled_for >= now
```

该视图由 API、CLI `reminders --pending` 和“查看待处理提醒”等确定性 CEO Assistant 短语共享。为保持兼容，无参数列表仍返回全部项目；`status=cancelled&time_scope=upcoming` 等显式组合继续受支持。

“查看我的提醒”使用待处理视图，并可单独汇总终态数量。它不会创建 Reminder，也不会从显式查询中隐藏终态记录。

## 后果

- 面向产品的 pending 结果排除 cancelled 与 triggered 项。
- 底层时间过滤保持可组合与向后兼容。
- 状态聚合继续集中管理，不引入第二个公开 Reminder 状态枚举。
