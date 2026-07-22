# ADR-056 — Deterministic Follow-up Interaction Boundary

Status: Accepted

## 背景

Waiting-For 写操作会创建或改变持久化业务状态。自然语言中的人名、事项、时间和动作可能存在歧义；LLM 分类或生成文本不能提供可重复的写入依据，也不能证明持久化成功。现有 Intent Safety 已采用 READ / WRITE / CHAT 显式 effect contract，并在歧义时优先读取。

## 决策

1. Waiting-For 写 Intent 只能由确定性规则识别，并在 `_assert_effect_contract()` 中显式声明为 WRITE。
2. 歧义输入不得直接创建或修改 Waiting-For、Reminder、Scheduler Job 或其他业务对象。
3. CEO Assistant 的自然语言 Waiting-For 创建必须先 Capture 为 pending Inbox Item，再由用户通过 Inbox ID Confirm。
4. 对既有 Waiting-For 的 follow-up、snooze、resolve、cancel、reopen 必须要求 canonical Waiting-For ID；标题或人名只能用于无副作用候选查询。
5. LLM 不能决定写操作、补猜必填字段、触发 mutation，或用生成文本证明写入成功。
6. 读取优先于歧义写入；缺少目标 ID 时返回候选并要求用户明确选择，保证零写入。
7. `FailureInfo` 的 code、category 与 details 是机器错误语义权威；Presenter 只能转换展示文本，不改变 HTTP status 或 CLI exit code。
8. 显式 API/CLI 创建 `POST /waiting-for` 与 `python -m cli waiting-for create` 不受自然语言两阶段限制，继续直接调用 canonical `WaitingForService`。

## 并发与成功证据

生命周期写入先读取当前 revision，再以该 revision 调用 mutation；Repository CAS 是最终并发边界。revision conflict 显式失败，不自动重试写操作，不追加重复 event。

成功响应必须来自 canonical Service 返回的持久化结果，并包含 Waiting-For ID、new revision、event type 和新的复查时间或终态。LLM 文本不是成功证据。

## 后果

- 用户可以自然读取与捕获，同时保留明确、可审计的写入边界。
- 自然语言创建多一步确认，但换取持久化幂等、崩溃恢复和重复创建防护。
- CEO Assistant 需要确定性 parser、handlers 与错误 Presenter，但不得变成通用 NLP 写入引擎。
- Waiting-For canonical lifecycle、API/CLI 显式入口和 FailureInfo 合同保持兼容。

## 不包含

本 ADR 不实现 intent、handler、Inbox target、API、CLI、Schema 或生产代码，也不批准 SP-017 实施。它不包含自动 Reminder、Scheduler、外部通知、Recurring、Web UI、Background agent、Knowledge、RBAC 或跨数据库事务。
