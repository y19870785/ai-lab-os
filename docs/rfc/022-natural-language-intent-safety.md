# RFC-022：Natural-Language Intent Safety

状态：Adopted

**Adoption Record**

| 字段 | 值 |
|---|---|
| SP | SP-012 |
| PR | [#25](https://github.com/y19870785/ai-lab-os/pull/25) |
| Approved Head | `ef9747a47648d382c89362e7265ba1eb3b17bf63` |
| Merge Commit | `d550ab8757b50e4d12587d5e71a0058089bd3821` |
| Merged At | `2026-07-17T10:12:19Z` |

## Problem Statement

SP-011 手工验收发现，“今天都有什么事？”和“今天都有哪些提醒？”会因宽泛的“今天”规则进入 Work Log 写路径。该错误发生在 LLM 调用前，切换真实 Provider 不会修复，并会让只读问句产生持久化副作用。

## Intent Precedence

确定性顺序为：Reminder 明确写操作、Reminder 明确只读操作、其他只读操作、显式 Work Log 写入、普通 Chat。`提醒我` 等创建标记优先于标题中偶然出现的“改期”等词。

## Effect Contract

`IntentDecision` 显式携带 `read`、`write` 或 `chat`。Reminder 列表与详情只能以 `read` 进入白名单 handler；取消、改期和创建为 `write`。响应 metadata 暴露 intent/effect，便于端到端验证。

## Read On Ambiguity

不确定输入不默认写入。Work Log 仅由“记录一下”“写一条工作记录”等命令，或“完成了”“处理了”“确认了”等明确已发生动作触发。普通问句进入只读 Reminder 路径或 Chat。

## Reminder Query Aliases

今天类查询统一使用 `time_scope=today` 并返回当天全部状态；“我今天有什么要做的”“接下来有什么提醒”“待处理提醒”等使用 `view=pending`。全部 Inbox 保持既有兼容语义。

## Failure Presentation

机器码保持 `reminder.target_required`、`reminder.time_required`、`reminder.time_unsupported`、`reminder.time_in_past`、`reminder.not_found` 与 `reminder.ambiguous`。CEO Assistant 通过集中 Presenter 返回中文可操作文案，不透传底层英文消息。

## Deterministic Boundary

Reminder 查询与错误引导不调用 LLM，也不显示 Mock/API Key 提示。普通 Chat 的 Provider 行为不变。

## Testing And Acceptance

单元测试固定优先级与 effect；真实 FastAPI lifespan、Composition Root、SQLite、Reminder Inbox 和 Memory 测试对比查询前后 Work Log、UserTask、Reminder 数量。手工验收按 `docs/acceptance/SP-012-intent-safety-reminder-query.md` 执行。

## Known Limitations

本 RFC 不实现 LLM 意图分类、多轮指代、模糊搜索、复杂相对时间、Recurring Reminder、外部通知或 Web UI。
