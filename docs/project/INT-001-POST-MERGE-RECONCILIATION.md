# INT-001 合并后治理对账（Post-Merge Reconciliation）

- 对账任务：INT-001A — INT-001 Post-Merge Reconciliation
- 状态：OPEN / DRAFT / PENDING_INDEPENDENT_REVIEW / NOT_READY / NOT_MERGE_AUTHORIZED / SELF_CLOSING
- 生效规则：本记录在 INT-001A Draft PR 经独立审查、Owner 授权并合并进入 `main` 时，自动成为 INT-001 最终权威对账记录。
- 递归规则：INT-001A / SELF_CLOSING / NO_RECURSIVE_RECONCILIATION；INT-001B / DO_NOT_CREATE。

## 合并事实（Merge Facts）

| 事实 | 权威值 |
|---|---|
| Feature PR | #70 — `INT-001: add shell-neutral trusted interaction adapter and Hermes MCP projection` |
| Approved Head | `696fc66e26d7a69fc2fb2a0dc67f33f7400f2912` |
| Authorized Base / Unique Parent | `49d77b6bd6bde3fe39eaecd5a7f8aa5b66249356` |
| Parent Count | `1` |
| Squash Merge Commit | `c3c71c7934e50725e4a82ef745245fcdb502811c` |
| Merge Time UTC | `2026-08-09T16:50:10Z` |
| main Quality Gate | `31324821391 / SUCCESS` |
| GitHub Linux non-real | `1775 passed / 6 skipped / 26 warnings` |
| real-test isolation | `10 passed / 5 skipped` |
| Ruff | SUCCESS |
| Real Provider | NO EVIDENCE OF EXECUTION |

PR #70 已 `MERGED / CLOSED`。Squash Merge Commit 的唯一父提交是批准的 Base，main Quality
Gate 的 Head 精确为 `c3c71c7934e50725e4a82ef745245fcdb502811c`。这些是已经完成的
历史事实；INT-001A 不重写产品实现或验收证据。

## 最终独立审查（Final Independent Review）

初轮独立审查发现以下五项 blocker，全部在最终 Approved Head 修复并经独立复核：

| 审查阻断项（Blocker） | 最终状态 | 已验证边界 |
|---|---|---|
| Modify policy/risk drift | RESOLVED / INDEPENDENTLY_VERIFIED | operation、policy reference 或 risk 漂移时 fail closed，不写 replacement Preview，不增加 revision |
| Recovery policy gate | RESOLVED / INDEPENDENTLY_VERIFIED | disabled/mismatched policy 不调用 canonical recover；matching policy 仍只委托 `InteractionService.recover()` |
| `final` terminality semantics | RESOLVED / INDEPENDENTLY_VERIFIED | `final` 表示 canonical terminality；`final=true` 不等于 business success |
| Runtime acceptance evidence completeness | RESOLVED / INDEPENDENTLY_VERIFIED | Direct ↔ MCP projection、unsafe Cancel 与 MCP Recovery no-reexecution 均有运行时证据 |
| Trusted adapter/transport provenance | RESOLVED / INDEPENDENTLY_VERIFIED | AI-Lab stamp `trusted-interaction/v1`、`direct` / `mcp-stdio`，caller 不能用 correlation 伪造权威 transport provenance |

最终 Approved Head：`696fc66e26d7a69fc2fb2a0dc67f33f7400f2912`。

## 最终治理状态（Final Governance State）

```text
INT-001:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
POST_MERGE_RECONCILED /
CLOSED_LOOP_COMPLETE /
ARCHIVED

ACC-INT-001 A-Q:
PASSED /
FINAL /
INDEPENDENT_REVIEW_PASSED

INT-001A:
SELF_CLOSING /
NO_RECURSIVE_RECONCILIATION

INT-001B:
DO_NOT_CREATE
```

`current_sp`、`current_governance_task` 与 `current_work` 均为 None。INT-001 不是 Product SP，
因此 `latest_merged_sp` 与 `latest_completed_sp` 继续为 SP-021，`next_candidate_sp` 与
`next_candidate_name` 继续为 None。

## 保持的产品与信任边界（Preserved Boundaries）

- Hermes Memory 不是 Business Fact Source；Hermes Conversation 不是 Approval Fact Source；
  Hermes Tool Response 不是 Final Success Proof。
- INT-001 合并了 Shell-neutral Adapter 与 local stdio MCP reference projection；没有接入真实 Hermes、
  企业微信或其他 Channel。
- 没有实现真实 identity binding、Workspace mapping、operation policy、ExecutionAdapter、
  VerificationAdapter 或 CanonicalCommitAuthority。
- INT-001A 只修改治理文档、机器状态与治理测试，不修改 Product code、Schema、Migration、Runtime、
  dependencies、lock file 或 CI workflow。
- PILOT-001 只提升为 `NEXT_CANDIDATE / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION /
  IMPLEMENTATION_NOT_APPROVED`，不构成授权、启动或 current work。
- REL-036 保持 `NOT_STARTED / NOT_APPROVED`。

## 质量候选项（Quality Candidates）

QUALITY-003 保持：

```text
CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED
```

QUALITY-004 保持：

```text
CANDIDATE / SAFETY_RELEVANT / NOT_STARTED / NOT_AUTHORIZED
```

INT-001A 不启动、修复、skip 或 xfail 上述候选项。所有本地验证使用非空无效 sentinel；如果
任何 real Provider 开始执行，验证必须立即停止。

## 版本与发布不可变事实（Version and Release Invariants）

- Version：`0.35.0`，未改变。
- `v0.35.0` annotated tag object：`99de47895b967bc41c3b1dcb3d2caaa630fcd4de`，未改变。
- `v0.35.0` peeled commit：`60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`，未改变。
- GitHub Release：Existing published Pre-release / unchanged。
- 不创建 `v0.36.0`、新 Tag 或新 Release。

## 授权边界（Authorization Boundary）

本 Draft PR 只等待 INT-001A 独立审查。不得自行转 Ready 或 Merge，不得创建 INT-001B，不得
启动 PILOT-001、REL-036 或任何真实 Shell/Channel 集成。INT-001A 合并进入 main 后，本记录自动
生效并闭环，不再创建递归 post-merge reconciliation。
