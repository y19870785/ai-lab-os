# AI-Lab 项目状态

**日期：** 2026-08-12
**源码版本：** v0.35.0 Alpha / GitHub Pre-release Published
**已验证发布基线：** `22f88d1da962fb436c48c19e5343fad8bf62f5f6` / Quality Gate run `29855987444`

## 当前治理状态

| 项目 | 状态 |
|---|---|
| 最近合并的 SP | SP-021 |
| 最近完成的 SP | SP-021 |
| 当前 Product SP | None |
| 当前治理任务 | None |
| 当前工作 | None |
| INT-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / CLOSED_LOOP_COMPLETE / ARCHIVED |
| QUALITY-004 | RESOLVED / IMPLEMENTED / FINAL_INDEPENDENT_REVIEW_PASSED / REAL_PROVIDER_ISOLATION_GUARD_ESTABLISHED / PILOT_SAFETY_BLOCKER_CLEARED |
| QUALITY-003 | CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED |
| PILOT-001 | PLANNING_BASELINE_APPROVED / FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED / P0_E_REVALIDATION_REQUIRED_AFTER_QUALITY_004 / P0_R_NOT_AUTHORIZED / PHASE_1_NOT_AUTHORIZED / PHASE_2_NOT_AUTHORIZED / REAL_PILOT_NOT_STARTED |
| ARCH-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| ARCH-001 Planning PR | #66 / MERGED / CLOSED / `4f9eab191fc0d99898ee69a2b42912017e4740e3` |
| RFC-032 | Adopted |
| ADR-069～072 | Accepted |
| 下一规划治理项 | None |
| STRAT-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| STRAT-001 Planning PR | #63 / MERGED / CLOSED / `b644c38064117a4dcb906c8607c782b67aedf1a6` |
| 下一候选 SP | None |
| RFC-031 | Adopted |
| ADR-067 / ADR-068 | Accepted |
| PR #62 | CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / IMPLEMENTATION_NEVER_AUTHORIZED |
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
| SP-021 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| ACC-021 | PASSED / FINAL（A～R 全部通过；FINAL_REVIEW_PASSED） |
| REL-035 | FINAL_RECONCILED / ARCHIVED |

STRAT-001 只建立可信业务操作系统定位、Agent Shell/业务核心所有权和 v0.36+ 路线基线。
当前 Product SP 与 Governance Task 均为 None。SP-021 已通过最终独立审查、ACC-021 A～R、PR #68
Squash Merge 与 main Quality Gate `31311699187`，并完成治理对账和封存。INT-001 已实现
Shell-neutral Adapter、fail-closed identity/policy authority 与本地 stdio MCP reference projection，
通过 ACC-INT-001 A～Q、最终独立审查、PR #70 Squash Merge 和 main Quality Gate `31324821391`，
并完成治理对账和封存。PILOT-001 规划基线已获批准并通过最终独立规划审查，固定为企业微信单 Owner 私聊、
`PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING` 与唯一 `user_task.create`。P0-E 的环境连接与工具隔离成功，但
validation suite 意外执行真实 Provider，因而被 QUALITY-004 阻断；这是本地测试凭据隔离安全缺陷，
不是 WeCom/MCP compatibility failure。QUALITY-004 Guard 已实现并通过最终独立安全审查，原 safety blocker
已清除；P0-E 仍需重新验证，P0-R、Phase 1、Phase 2 与实现仍未授权，真实 Pilot 尚未启动。
REL-036 未启动，版本、Tag 和 Release 未改变。
STRAT-001 已通过最终独立审查、合并和 main Quality Gate，并完成 post-merge reconciliation
与封存。ARCH-001 已通过独立审查、PR #66 Squash Merge、main Quality Gate 和 post-merge
reconciliation 并封存；该结果不构成任何实现授权。

ARCH-001 已完成当前实现审计并提出 `trusted-interaction/v1` 合同基线：Preview 与 Confirmation 是 AI-Lab
canonical facts，identity/Workspace 映射失败关闭，Tool/HTTP/外部 ack 不能替代 Verified Result，不确定
执行进入显式 Recovery。该结论不改变 v0.35.0 产品行为。

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
Implementation、正式验收、独立证据复核、功能合并、main Quality Gate 与治理对账均已完成；Current Product SP 与 Current Governance Task 均为 None。

REL-035 已按 `v0.35.0 Alpha — Local Daily Operating Loop` 发布收口规划完成 v0.34.0
数据兼容、Local Daily 配置升级、验证矩阵和独立授权状态机。Release PR #60 已合并，
main Quality Gate `30744879482` 成功；annotated Tag 与 GitHub Pre-release 已远端验证，
最终发布对账完成并封存。

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
- 发布状态：ALPHA / PRE_RELEASE_PUBLISHED
- 当前已发布 Tag：`v0.35.0`；上一已发布 Tag：`v0.34.0`
- v0.35.0 Tag：ANNOTATED / REMOTE_VERIFIED
- v0.35.0 GitHub Release：目标类型为 Pre-release；PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED
- 二进制附件：不发布 wheel 或 sdist，仅使用 GitHub 自动源码归档
- 外部发布事实：实际 Tag 存在性与目标、Release 发布状态、URL 和时间以 GitHub Tags and GitHub Releases 为权威来源
- v0.35.0：PRE_RELEASE_PUBLISHED

Latest Merged SP 与 Latest Completed SP 均为 SP-021；Current Product SP、Current Governance Task 与 Current Work 均为 None。SP-021 已完成合并、main Quality Gate、ACC-021 最终验收、治理对账与封存。INT-001 已完成 ACC-INT-001 A～Q、最终独立审查、合并、main Quality Gate、治理对账与封存；真实 Hermes/Channel 未接入。PILOT-001 规划基线已获批准并通过最终独立规划审查，实现仍未授权，真实 Pilot 尚未启动。当前产品版本为 `0.35.0` Alpha GitHub Pre-release；annotated Tag 与 Release 未变化。该发布不等于 production-ready。
