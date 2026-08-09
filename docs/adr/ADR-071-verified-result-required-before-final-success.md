# ADR-071：最终成功必须先形成 Verified Result

- Status: Accepted
- Date: 2026-08-06
- Governance Task: ARCH-001
- Related RFC: RFC-032
- Accepted by: ARCH-001 / PR #66 / Merge Commit `4f9eab191fc0d99898ee69a2b42912017e4740e3`
- Implementation: NOT_APPROVED / NOT_STARTED

## 背景（Context）

Tool invocation accepted、ToolResult success、HTTP 2xx 与外部 acknowledgement 只描述各自边界的返回，不能
证明外部最终状态、canonical business commit 或两者一致。timeout 后盲重试还可能重复不可逆副作用。

## 决策（Decision）

Interaction 只有在 AI-Lab 按 operation-specific verifier 形成 Verified Result，并完成该 operation 要求的
canonical commit 后，才能进入 `SUCCEEDED`。验证可以是内部事务后的 read-back、外部 read-after-write、
status query、webhook、poll 或 reconciliation；证据必须关联 Interaction ID、Execution ID、Workspace、
canonical object/revision、external reference、method、redacted digest、verifier 与时间。

外部动作成功但 canonical commit 失败，或执行结果无法判断时，进入 `RECOVERY_REQUIRED`；canonical commit
成功但响应丢失时，Status/idempotency 返回原结果。UNCERTAIN 状态禁止重放原动作，只允许 verification 或
受控 recovery。

## 后果（Consequences）

正面结果：Shell 无法伪造成功；断线、重试和异步执行可以恢复；失败与不确定性对用户可见。

代价与风险：每类外部动作必须定义 verifier、evidence retention、timeout 与 recovery owner；部分操作会延迟
最终响应。ARCH-001 不实现 executor、worker、webhook、poller 或 recovery queue。

## 被拒绝的方案（Rejected Alternatives）

- Tool response 或 HTTP 2xx 作为 final success：只证明 transport/invocation 层。
- 外部 acknowledgement 自动提交 canonical success：ack 可能只是受理。
- timeout 后自动重试所有操作：结果未知时可能重复副作用。

## 状态与授权（Status and Authorization）

本 ADR 已由 ARCH-001 / PR #66 合并接受。Accepted 不构成运行时实现授权。
