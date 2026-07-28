# AI-Lab Project Status

**Date:** 2026-07-29
**Source Version:** v0.34.0 Alpha / Release Authorized
**Verified release baseline:** `22f88d1da962fb436c48c19e5343fad8bf62f5f6` / Quality Gate run `29855987444`

## Current governance state

| Item | State |
|---|---|
| SP-014 | APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-014B | APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED |
| ACC-014 | PASSED / FINAL（A～L 全部通过） |
| SP-015 | APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-015A | APPROVED / MERGED / RECONCILED / ARCHIVED |
| SP-015R | APPROVED / MERGED / RECONCILED / ARCHIVED |
| SP-016 | APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / COMPLETED / ARCHIVED |
| ACC-016 | PASSED / FINAL（A～J 全部通过） |
| SP-017 | APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| ACC-017 | PASSED / FINAL（A～O 全部通过） |
| RFC-026 | Adopted |
| ADR-056 / ADR-057 | Accepted |
| SP-018 | APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED |
| RFC-027 | Adopted |
| ADR-058 / ADR-059 / ADR-060 | Accepted |
| ACC-018 | PASSED / FINAL（A～O 全部通过） |
| SP-019 | IMPLEMENTATION_APPROVED / PHASE_0_ACCEPTED / DAILY_REVIEW_ACCEPTED / PENDING_MERGE |
| RFC-028 / ADR-061 / ADR-062 | IMPLEMENTED / ACC-019 PASSED / PENDING MERGE |
| ACC-019 | PASSED / FINAL（A～M 全部通过） |

根目录 `project_state.json` 是唯一机器可读仓库治理状态与稳定发布授权源；本页是便于人工阅读的摘要。当前 GitHub main HEAD、Pull Request 状态和最新 Workflow run 是通过 Git/GitHub 实时查询的外部事实，不在治理文件中维护自指的 current-main 镜像；运行时产品版本仍只来自 `pyproject.toml`。

## Product baseline

v0.34.0 Alpha 之上的 v0.35 开发线已合并 canonical Work Log、Workspace-safe query、legacy 只读投影以及统一 API/CLI/CEO/Inbox/Agenda/Brief 边界。ACC-018 A～O 与 post-merge verification 均已通过。

SP-014 通过 PR #32 合并，SP-014B 通过 PR #33 合并，最终治理对账通过 PR #34 合并。ACC-014 的场景 A～L 均为 PASSED，场景 K 的中文小时兼容缺口已由 SP-014B 修复并在 main 复验。

## Quality baseline

最终发布提交前的已验证 main 基线对应 GitHub Quality Gate run `29855987444`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1163 passed, 6 skipped, 27 warnings`。该 commit 是历史验证基线，不是 tracked 文件对自身当前 commit 的声明。真实 Provider 测试不属于普通门禁。

SP-017 feature merge main `32bb9c0a939c65f2278fc2b6be8d072fb2e3656a` 的 post-merge GitHub Quality Gate run `30006958413`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1239 passed, 6 skipped, 27 warnings`。该记录不改变 v0.34.0 Release 历史基线。

SP-018 feature merge main `83ecb557fedd1d898712afc59ad13b3e0a684413` 的自动 push Quality Gate run `30196719409`：Ruff SUCCESS，pytest (non-real) SUCCESS。ACC-018 A～O、本地全量回归与 post-merge smoke 均已通过；该记录不改变 v0.34.0 Release 历史基线。

SP-018A reconciliation PR #47 已合并为 main `4e0d730a8bfdefa6277c7526a028e7247d7ddc43`；自动 push Quality Gate run `30198434517` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。

SP-019 Planning PR #48 已由 Approved Planning Head `282dd939ff264b0f23d5070b6f632aa0442531ea` Squash Merge 为 main `e7fc5b1dd66ff7828c1697bfd5610f300599eee5`，合并时间 `2026-07-26T14:19:41Z`；自动 push Quality Gate run `30205853257` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。后续 Owner 已批准 SP-019 Implementation，Phase 0 PR #50 已合并、通过 post-merge Quality Gate 并完成独立验收。

## Release state

- 源码版本：`0.34.0`
- 成熟度：Alpha / local-first / single-user-oriented
- 发布状态：ALPHA / RELEASE_AUTHORIZED
- 授权 Tag：`v0.34.0`
- GitHub Release 类型：Pre-release
- 二进制附件：不发布 wheel 或 sdist，仅使用 GitHub 自动源码归档
- 外部发布事实：实际 Tag 存在性与目标、Release 发布状态、URL 和时间以 GitHub Tags and GitHub Releases 为权威来源

Current Product SP 为 SP-019，Current Governance Task 为 None，Latest Completed SP 为 SP-018。SP-018 已合并、验收、完成 post-merge verification 与对账并封存；ACC-018 A～O 均为 PASSED / FINAL。SP-019 Planning Baseline 已 APPROVED / MERGED / RECONCILED，Owner 已批准 Implementation；Phase 0 UserTask Workspace Query Closure 已 ACCEPTED。Daily Review 已在 Approved Implementation Head `1f2975503cd79047137a4a9f47096668fd4341c5` 上通过 ACC-019 A～M，当前为 ACCEPTED / PENDING_MERGE。SP-019 尚未合并或完成，当前产品版本仍为 `0.34.0`。
