# ADR-063 — Daily Review Action Hints as Pure Deterministic Presentation

- Status: Accepted
- Date: 2026-07-29
- SP: SP-020

## 背景（Context）

Daily Review 已输出 canonical `source_type`、`source_id`、`status` 与
`reason_code`，但 Presenter 目前只展示事实。SP-020 希望用户能从 Review 清楚看到
下一步可做什么，同时必须保持 Daily Review 纯只读、确定性、无 LLM、无副作用。

若 Presenter 猜测动作、直接 mutation，或建立新的 Action 数据源，就会绕过现有领域
服务的 Workspace、revision、idempotency、preview/confirm 与 Saga 合同。

## 决策（Decision）

Action Hint 是纯只读 presentation contract，不是 command，也不是执行授权。

Hint 只能由以下事实确定：

```text
source_type
current status
reason_code
current canonical domain contract
```

每条 hint 至少包含：

```text
source_type
canonical source_id
status
reason_code
allowed_action
required_arguments
requires_revision
requires_confirmation
available_entrypoints
```

`available_entrypoints` 只列出当前真实存在并符合该动作安全合同的入口。一个
`allowed_action` 至少有一个真实、安全入口即可展示，不要求 API、CLI 与 CEO Assistant
三者同时存在。尚未存在的入口不得被描述为可用；没有任何真实安全入口时，不得生成
该 action hint。

revision、idempotency、durable claim/Saga 与 confirmation 按动作分别声明。只有该
动作真实需要时，`requires_revision` 或 `requires_confirmation` 才为 true；不得把
所有 mutation 套入同一个规则。

Action Hint：

- 不调用 Provider 或 LLM；
- 不选择“最佳”动作；
- 不执行或调度动作；
- 不发布 mutation event；
- 不拥有数据库、不持久化、不创建 snapshot；
- 不改变 Daily Review 日期、分类、去重、排序或分页；
- 只映射到真实存在的 UserTask、Reminder、Waiting-For、Inbox 与 Work Log 能力；
- 明确 Work Log 只有 create/get/list，不伪造 edit/complete/delete。

执行仍由用户通过明确 canonical ID 与必要参数委托现有 canonical domain service。模糊
自然语言遵守：

```text
Read directly
Capture ambiguously
Confirm persistently
Mutate explicitly by canonical ID
```

## 结果（Consequences）

优点：

- 用户能从同一 Review 看见真实、可审计的下一步；
- Daily Review 与 Presenter 继续保持零写入、零 LLM；
- 不产生第二套 action truth 或 mutation；
- 动作能力漂移可由治理测试与契约测试发现。

代价：

- 每个动作映射必须跟随真实领域合同更新；
- 一个动作只需至少一个真实安全入口；不会为矩阵对称性虚构或补齐其他入口；
- Action Hint 与实际执行需要分别测试。

## 拒绝方案

- LLM 生成或选择 action：不确定且可能伪造能力。
- Presenter 内直接调用 mutation：破坏只读与确认边界。
- Action 数据库或 Review snapshot：增加第二事实源和恢复负担。
- 通用 Command Bus 重写：范围过大，且现有 canonical services 已是执行边界。

## 验证要求

ACC-020 必须验证：

- 同一 Review 输入生成完全相同的 hints；
- 每个 hint 的 `available_entrypoints` 至少包含一个真实安全入口，且不包含尚未存在
  的入口；
- unsupported status/reason 不生成伪动作；
- 生成 hint 时数据库、EventBus、Scheduler、Provider call 均无副作用；
- 执行动作必须经过 canonical service，并按该动作自身声明满足 Workspace、revision、
  idempotency、durable claim/Saga 或 confirmation 合同。

## 治理

本 ADR 已随独立审查通过并合并的 SP-020 Planning Baseline Accepted。它不批准
Action Hint 实现，也不改变 RFC-028、ADR-061 或 ADR-062 的既有 Daily Review
只读合同。
