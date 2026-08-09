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
| F | duplicate confirmation deterministic；跨两个独立 DatabaseManager/SQLite connection 的 concurrent create 原子 claim；same key/different payload conflict 且无 orphan duplicate | `test_confirmation_cas_idempotency_and_cancel`；`test_acc_021_f_idempotency_and_conflict`；`test_create_idempotency_claim_is_atomic_across_independent_connections` |
| G | pre-execution cancel、duplicate semantics、terminal/uncertain cancel 拒绝 | service cancel test；`test_acc_021_g_l_m_n_uncertain_is_persisted_and_never_blind_retried` |
| H | canonical Execution ID、attempt、idempotency、audit | ACC happy path |
| I | acknowledgement 不能产生 `SUCCEEDED` | persistence restart test；ACC happy path |
| J | VerificationPort 只能提供外部观察；`VerifiedResult` + AI-Lab-owned `CanonicalCommitEvidence` 才成功，恶意 verifier 不能自证 canonical commit | persistence restart test；ACC happy path；`test_acc_021_j_verified_external_result_without_canonical_commit_cannot_succeed` |
| K | verification failure 进入 recovery，不能 success | `test_acc_021_k_verification_failure_requires_recovery` |
| L | timeout/uncertain 不 blind retry，进入 recovery | uncertain acceptance test |
| M | timeout 后 Status 返回 persisted canonical state | uncertain acceptance test |
| N | execution intent transaction 提交后、port outcome 持久化前崩溃；Composition Root 重建后保留原 Execution ID/idempotency/attempt 并显式 reconcile，禁止第二次 execute | `test_execution_intent_crash_reconciles_after_composition_root_restart`；persistence restart test；uncertain acceptance test |
| O | late/duplicate/out-of-order command 不覆盖新 revision | `test_acc_021_o_r_late_and_cross_workspace_commands_fail` |
| P | 统一 FailureInfo 与 sensitive details redaction | verification failure acceptance test |
| Q | injected failure rollback，无 partial fact/state/audit | `test_acc_021_q_atomic_verified_result_transition` |
| R | Workspace A 的 canonical IDs 无法由 Workspace B 操作 | cross-Workspace unit/acceptance tests |

## 独立审查 blocker 补强

- Canonical commit authority：`VerificationObservation` 不含 canonical commit 成功字段；required commit 由 AI-Lab-controlled `CanonicalCommitAuthority` 产生并持久化 `CanonicalCommitEvidence`。
- Execution crash window：持久化 `EXECUTING / ATTEMPTED` 后崩溃，显式 `recover` 先转入 `RECOVERY_REQUIRED`，只执行 verification/recovery，不再次调用 `ExecutionPort`。
- Create idempotency atomicity：数据库唯一键先原子 claim canonical identity；冲突路径不允许覆盖先到的 `interaction_id`。
- Approval authority：caller 自报 role、missing evidence 和 invalid evidence 均 fail closed；只有 AI-Lab-controlled `ApprovalAuthority` 验证的绑定证据可形成 Approval。Confirmation 仍不能替代 Approval。

## 判定边界

本文件不宣称 ACC-021 `PASSED / FINAL`。Draft PR 的自动化结果必须经独立审查；Ready 与 Merge 需要后续 Owner 明确授权。Hermes、企业微信、MCP、真实外部 Adapter 和真实 Provider 不属于本验收。
