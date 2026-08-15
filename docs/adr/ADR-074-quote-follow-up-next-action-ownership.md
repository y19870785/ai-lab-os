# ADR-074：Quote、Follow-up 与 Next Action 所有权

## 状态

- **状态**：PROPOSED / NOT_ACCEPTED
- **任务**：SP-022
- **日期**：2026-08-15
- **相关 RFC**：RFC-034
- **实现状态**：NOT_AUTHORIZED

## 背景

SP-022 需要 Customer、Contact、Follow-up 与 Next Action，但仓库已有 Waiting-For、Daily Review 与 Action Hint。若只写“复用”而不裁决 identity、生命周期和投影方向，实现可能建立双 canonical owner。

## 决策

### 客户与联系人

Customer 与 Contact 是 Quote bounded context 内的 canonical entity，不引用仓库中另一套同名 canonical domain，因为当前 canonical main 没有受支持的 Customer/Contact owner。它们使用独立稳定 ID、完整 WorkspaceKey 与 revision；Contact 必须引用同 workspace Customer。未来若建立企业级 Customer master，迁移需要独立 ADR 和显式 ID mapping，不能并行保留两个 owner。

### 跟进事实

选择：`Waiting-For canonical reference/projection`。

Quote Request 只保存可选 `waiting_for_id` 及 linkage audit，不复制 Waiting-For 的责任人、状态、截止日期、follow-up history 或 reopen/cancel 生命周期。需要跟进时由获准的 Slice B 通过幂等命令创建或链接同 workspace Waiting-For；读取时以 Waiting-For canonical fact 为准。这样保留既有客户/外部依赖语义，避免第二套 Follow-up 状态机。

### 下一行动

Next Action 是 Quote Request aggregate 拥有的 child value：

- ID：`qna_<32 lowercase hex>`，在 Quote aggregate 内稳定且不可复用；
- 生命周期：随 Quote transition 创建、替换或关闭，受 Quote revision/CAS 保护；
- 内容：动作摘要、责任 owner reference、due-at 与来源 transition；
- 投影方向：Quote Request -> Quote read model -> Daily Review / Action Hint；
- Waiting-For 可作为 Next Action 的外部依赖引用，但不拥有 Next Action；
- Daily Review 只消费 canonical read model，不创建、拥有或修改 Quote/Next Action；
- Action Hint 只是确定性展示/preview，不是 canonical fact、授权或执行结果。

## 后果

- Quote bounded context 是 Customer、Contact、Quote Request 和 Next Action 的唯一 owner。
- Waiting-For 是 Follow-up 事实的唯一 owner。
- Daily Review 与 Action Hint 均为单向消费者，不反向写入 Quote。
- 跨 workspace linkage 一律返回 `quote.workspace_mismatch`，不得建立引用。
- Slice C 可以独立实现 read projection，而不会把展示层混入 Slice A 的写入所有权。

## 未选择方案

- Quote child Follow-up：会复制 Waiting-For 的状态、责任人与截止事实。
- 新独立 Follow-up domain：没有新的业务语义足以支持第二 owner。
- Daily Review 拥有 Next Action：违反 read-model 边界并形成反向写入。

## 授权

本 ADR 为 `PROPOSED / NOT_ACCEPTED`。它只关闭规划歧义，不授权领域模型、持久化、projection 或入口实现。
