# ADR-075：Inbox 到 Quote Request 的可靠协调

## 状态

- **状态**：PROPOSED / NOT_ACCEPTED
- **任务**：SP-022
- **日期**：2026-08-15
- **相关 RFC**：RFC-034
- **实现状态**：NOT_AUTHORIZED

## 背景

Inbox 与 Quote Request 属于独立持久化边界，不能假设跨数据库原子事务。进程可能在 claim、target create、verification、linkage 或 completion 任一阶段终止；恢复合同必须在实现前固定。

## 决策

复用 Unified Inbox 的 durable claim/Saga 模式，阶段固定为：

```text
CLAIMED -> TARGET_CREATED -> TARGET_VERIFIED -> TARGET_LINKED -> COMPLETED
```

1. **claim**：先验证 command/envelope WorkspaceKey 与已认证请求上下文一致，再以 Inbox item ID、完整 WorkspaceKey、resolution type=`QUOTE_REQUEST` 和 idempotency key 建立唯一 durable claim；mismatch 在 claim/idempotency lookup 前返回 `quote.workspace_mismatch / permission_denied`。
2. **target create**：调用 Quote create，传递固定 namespace `full WorkspaceKey + operation + idempotency_key`；不直接写 Quote 数据库。同 workspace 不同 operation 或不同 workspace 的相同 key 字符串相互独立。
3. **canonical verification**：按相同 WorkspaceKey read-back Quote，验证 ID、revision、state 与 idempotency result。
4. **target linkage**：在 claim 中 CAS 保存 Quote ID、verified revision 与 QuoteAuditRecord correlation；重复 linkage 返回原结果。
5. **completion**：仅在 linkage durable 后将 Inbox resolution 标为 COMPLETED，并再次读取确认终态。

任何阶段失败都持久化 `FailureInfo`、stage、attempt、trace/correlation、retryable 与最后验证证据。不得用内存锁、单进程任务或跨库事务声明正确性。

## 崩溃与重试矩阵

| 观察状态 | 恢复动作 | 禁止行为 |
|---|---|---|
| Inbox 已 CLAIMED，Quote 未创建 | 使用原 idempotency key 重试 create | 换 key 创建第二 Quote |
| Quote 已创建，Inbox 未完成 | canonical read-back，补写 linkage，再完成 | 删除已验证 Quote 或盲目重建 |
| TARGET_CREATED 但 verification 未记录 | read-back 并校验 workspace/revision | 仅凭 create response 宣称成功 |
| TARGET_LINKED，completion 未提交 | CAS 重试 completion | 重复 target create |
| 重复 Inbox 事件/请求 | 同 namespace 同 payload 返回原 claim 和 QuoteMutationResult | 新建 claim 或重复 QuoteAuditRecord |
| persistence outcome unknown | 保持 pending，按原 key reconcile | 标记成功或静默丢弃 |
| projection failure | Quote 保持成功，记录 repair cursor | 回滚 canonical Quote |

## 协调扫描与修复

- scanner 只读取未完成或 outcome unknown 的 claims，按稳定分页与 WorkspaceKey 隔离处理。
- 每条 repair 先查询 claim，再查询 canonical Quote；所有推进使用 claim revision/CAS。
- Quote 存在且验证匹配时补 linkage/completion；scoped lookup 无结果时不得查询其他 workspace，只能用原 namespace 重试 create。
- foreign Quote/Customer/Contact/Waiting-For ID 与 absent ID 对 caller 均表现为 `quote.not_found / not_found`；scanner 不得通过错误码或 fallback lookup 泄露存在性。
- envelope workspace mismatch 在 repository/idempotency lookup 前返回 `quote.workspace_mismatch / permission_denied`；同 namespace 的 payload conflict 返回 `quote.idempotency_conflict / conflict`，canonical 数据不一致时 fail closed 并等待人工处置。
- repair 可重复运行；同一 claim 最多关联一个 Quote，同一 idempotency result 不重复产生 QuoteAuditRecord 或 projection event。

## 最终状态与证据

成功终态必须同时具备：Inbox `COMPLETED`、唯一 Quote linkage、Quote canonical read-back、匹配 revision、idempotency result、匹配的 QuoteAuditRecord，以及由这些证据形成的 QuoteMutationResult。失败终态必须保留 stage、稳定 failure code、最后已知 canonical 状态、retryability 和人工恢复指引。Slice B 不构造 Interaction VerifiedResult/AuditEvidence；只有另行授权的 Slice D 才能以真实 Interaction/Execution identity 投影 Interaction evidence。

## 后果与授权

该设计允许任意阶段进程终止后恢复，并明确不依赖跨数据库原子事务。它是 Slice B 的规划合同，状态为 `PROPOSED / NOT_ACCEPTED`；Slice B 及任何 scanner/repair 实现均需独立授权。
