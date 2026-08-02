# AI-Lab 项目状态

**日期：** 2026-08-02
**源码版本：** v0.35.0 Alpha / Release Candidate / Not Published
**已验证发布基线：** `22f88d1da962fb436c48c19e5343fad8bf62f5f6` / Quality Gate run `29855987444`

## 当前治理状态

| 项目 | 状态 |
|---|---|
| 最近合并的 SP | SP-020 |
| 最近完成的 SP | SP-020 |
| 当前 Product SP | None |
| 当前治理任务 | REL-035 |
| 下一候选 SP | None |
| DOCS-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / RECONCILED / ARCHIVED |
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
| SP-019 | APPROVED / MERGED / POST_MERGE_VERIFIED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| RFC-028 | Adopted |
| ADR-061 / ADR-062 | Accepted |
| ACC-019 | PASSED / FINAL（A～M 全部通过） |
| SP-020 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED |
| RFC-029 | Adopted |
| ADR-063 / ADR-064 | Accepted |
| ACC-020 | PASSED / FINAL（A～V 全部通过；独立证据复核 APPROVED） |
| REL-035 | IMPLEMENTATION_APPROVED / IMPLEMENTATION_IN_PROGRESS / SOURCE_VERSION_UPDATED / RELEASE_DOCUMENTATION_UPDATED / RELEASE_CANDIDATE_VALIDATED / DRAFT_PR_OPEN / PENDING_INDEPENDENT_REVIEW |

```text
SP-020:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
ACC_020_PASSED /
INDEPENDENT_EVIDENCE_REVIEW_APPROVED /
RECONCILED /
ARCHIVED

ACC-020:
PASSED / FINAL

Approved Implementation Head:
1c9b69ee45b4e1545b67ecd841cc217e23d4f38f

Acceptance Evidence Head:
7a0944f4ad1deadefe636bf5abc3d30175de0b4d

Formal Run:
ai-lab-acc020-formal-20260730-175832-eda685f89c274e6cb520c0aaa964b3dc

Provider Calls:
0

Evidence Review:
APPROVED

Feature Merge Commit:
9ea4b72241bd855319231c09fa6b80c112a14305

Main Quality Gate:
30687851816 / SUCCESS

Reconciliation PR:
58
```

根目录 `project_state.json` 是唯一机器可读仓库治理状态与稳定发布授权源；本页是便于人工阅读的摘要。当前 GitHub main HEAD、Pull Request 状态和最新 Workflow run 是通过 Git/GitHub 实时查询的外部事实，不在治理文件中维护自指的 current-main 镜像；运行时产品版本仍只来自 `pyproject.toml`。

## 产品基线

v0.34.0 Alpha 之上的 v0.35 开发线已合并 canonical Work Log 与 Daily Review。Daily Review 通过唯一 `DailyReviewService` 确定性聚合 Work Log、UserTask、Waiting-For、Reminder 与 Inbox，并由 API、CEO Assistant 和兼容 `/brief` 共用；ACC-019 A～M 与 post-merge verification 均已通过。

SP-020 已建立 Planning Baseline，方向为 Windows Local Daily Profile、直接复用现有
`DailyReviewService` 的正式 CLI、纯确定性 Action Hint、canonical
Review-to-Action 委托，以及 restart / Quiescent Backup / isolated restore 验收。
Implementation、正式验收、独立证据复核、功能合并、main Quality Gate 与治理对账均已完成；Current Product SP 为 None，Current Governance Task 为 REL-035。

REL-035 已获 Implementation 授权，按 `v0.35.0 Alpha — Local Daily Operating Loop` 的
发布收口规划验证 v0.34.0 数据兼容、Local Daily 配置升级、验证矩阵和独立授权状态机。
源码版本与 Release Notes 已更新为 `0.35.0`；Tag 与 GitHub Release 均未授权、未创建，
当前 Release Candidate 不等于已发布版本。

DOCS-001 已通过独立审查。Approved Head
`d7a6662dddaac87b41562e2348f69e04112b2be4` 由 PR #55 Squash Merge 为
`2d04f1b8574fde43b1d64a53d1ad22573073a4ef`，合并时间
`2026-07-29T14:43:26Z`；main Quality Gate run `30462290819` 为 SUCCESS。
该任务覆盖 176 个 Git 跟踪 Markdown 文件，并建立语言政策、完整清单、统一术语表
与自动化治理门禁；现已完成对账并封存。

SP-014 通过 PR #32 合并，SP-014B 通过 PR #33 合并，最终治理对账通过 PR #34 合并。ACC-014 的场景 A～L 均为 PASSED，场景 K 的中文小时兼容缺口已由 SP-014B 修复并在 main 复验。

## 质量基线

最终发布提交前的已验证 main 基线对应 GitHub Quality Gate run `29855987444`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1163 passed, 6 skipped, 27 warnings`。该 commit 是历史验证基线，不是 tracked 文件对自身当前 commit 的声明。真实 Provider 测试不属于普通门禁。

SP-017 feature merge main `32bb9c0a939c65f2278fc2b6be8d072fb2e3656a` 的 post-merge GitHub Quality Gate run `30006958413`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1239 passed, 6 skipped, 27 warnings`。该记录不改变 v0.34.0 Release 历史基线。

SP-018 feature merge main `83ecb557fedd1d898712afc59ad13b3e0a684413` 的自动 push Quality Gate run `30196719409`：Ruff SUCCESS，pytest (non-real) SUCCESS。ACC-018 A～O、本地全量回归与 post-merge smoke 均已通过；该记录不改变 v0.34.0 Release 历史基线。

SP-018A reconciliation PR #47 已合并为 main `4e0d730a8bfdefa6277c7526a028e7247d7ddc43`；自动 push Quality Gate run `30198434517` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。

SP-019 Planning PR #48 已由 Approved Planning Head `282dd939ff264b0f23d5070b6f632aa0442531ea` Squash Merge 为 main `e7fc5b1dd66ff7828c1697bfd5610f300599eee5`，合并时间 `2026-07-26T14:19:41Z`；自动 push Quality Gate run `30205853257` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。后续 Owner 已批准 SP-019 Implementation，Phase 0 PR #50 已合并、通过 post-merge Quality Gate 并完成独立验收。

SP-019 Feature PR #51 已由 Acceptance Evidence Head `420da28664914fda8ccbecadf90947380ec43473` Squash Merge 为 main `a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`，合并时间 `2026-07-28T17:18:41Z`；自动 push Quality Gate run `30382312419` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。Approved Implementation Head 为 `1f2975503cd79047137a4a9f47096668fd4341c5`，ACC-019 A～M 为 PASSED / FINAL。

## 发布状态

- 源码版本：`0.35.0`
- 成熟度：Alpha / local-first / single-user-oriented
- 发布状态：ALPHA / RELEASE_CANDIDATE / NOT_PUBLISHED
- 上一已发布 Tag：`v0.34.0`
- v0.35.0 Tag：NOT_AUTHORIZED / NOT_CREATED
- v0.35.0 GitHub Release：NOT_AUTHORIZED / NOT_CREATED；目标类型为 Pre-release
- 二进制附件：不发布 wheel 或 sdist，仅使用 GitHub 自动源码归档
- 外部发布事实：实际 Tag 存在性与目标、Release 发布状态、URL 和时间以 GitHub Tags and GitHub Releases 为权威来源
- v0.35.0：RELEASE_CANDIDATE_VALIDATED / NOT_PUBLISHED

Latest Merged SP 与 Latest Completed SP 均为 SP-020，Current Product SP 与 Next Candidate SP 均为 None，Current Governance Task 为 REL-035。SP-020 Feature PR #57 已 Squash Merge 至 main `9ea4b72241bd855319231c09fa6b80c112a14305`（`2026-08-01T06:29:58Z`），main Quality Gate `30687851816` 为 SUCCESS；SP-020A 对账载体为 PR #58。ACC-020 A～V、独立证据复核、治理对账与封存均已完成。当前产品版本为 `0.35.0` Release Candidate；`v0.35.0` Tag 与 GitHub Pre-release 未授权、未创建。SP-020 不等于 production-ready，External Notification、Recurring Reminder、Web UI、强身份/RBAC 与多租户边界仍未实现。
