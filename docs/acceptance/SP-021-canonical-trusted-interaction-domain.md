# ACC-021 Canonical Trusted Interaction Domain 验收基线

- Product SP：SP-021
- 状态：AUTOMATED EVIDENCE IN DRAFT PR / PENDING INDEPENDENT REVIEW / NOT FINAL
- Real Provider：禁止调用
- 外部系统：仅 deterministic Reference ports

## 场景矩阵

| 场景 | 验证目标 | 自动化证据 |
| --- | --- | --- |
| A | Canonical creation、ID、Workspace/actor、request/trace、revision、audit | `test_creation_is_canonical_idempotent_and_audited`；`test_acc_021_a_c_h_i_j_canonical_happy_path` |
| B | missing identity/Workspace、conflict 与 cross-Workspace fail closed | `test_identity_and_workspace_fail_closed`；`test_cross_workspace_read_is_rejected` |
| C | Preview 零 execution、持久化 revision/expiry/audit | `test_preview_modify_supersedes_and_stale_confirm_fails`；ACC happy path |
| D | Modify supersedes v1，v2 需 fresh confirmation | `test_preview_modify_supersedes_and_stale_confirm_fails` |
| E | exact revision、wrong actor/Workspace、expired/stale Preview | service unit tests 与 expiry tests |
| F | duplicate confirmation deterministic；same key/different payload conflict | `test_confirmation_cas_idempotency_and_cancel`；`test_acc_021_f_idempotency_and_conflict` |
| G | pre-execution cancel、duplicate semantics、terminal/uncertain cancel 拒绝 | service cancel test；`test_acc_021_g_l_m_n_uncertain_is_persisted_and_never_blind_retried` |
| H | canonical Execution ID、attempt、idempotency、audit | ACC happy path |
| I | acknowledgement 不能产生 `SUCCEEDED` | persistence restart test；ACC happy path |
| J | VerifiedResult + required canonical commit 才成功 | persistence restart test；ACC happy path |
| K | verification failure 进入 recovery，不能 success | `test_acc_021_k_verification_failure_requires_recovery` |
| L | timeout/uncertain 不 blind retry，进入 recovery | uncertain acceptance test |
| M | timeout 后 Status 返回 persisted canonical state | uncertain acceptance test |
| N | restart 恢复 aggregate、facts、idempotency、verification/recovery | persistence restart test；uncertain acceptance test |
| O | late/duplicate/out-of-order command 不覆盖新 revision | `test_acc_021_o_r_late_and_cross_workspace_commands_fail` |
| P | 统一 FailureInfo 与 sensitive details redaction | verification failure acceptance test |
| Q | injected failure rollback，无 partial fact/state/audit | `test_acc_021_q_atomic_verified_result_transition` |
| R | Workspace A 的 canonical IDs 无法由 Workspace B 操作 | cross-Workspace unit/acceptance tests |

## 判定边界

本文件不宣称 ACC-021 `PASSED / FINAL`。Draft PR 的自动化结果必须经独立审查；Ready 与 Merge 需要后续 Owner 明确授权。Hermes、企业微信、MCP、真实外部 Adapter 和真实 Provider 不属于本验收。
