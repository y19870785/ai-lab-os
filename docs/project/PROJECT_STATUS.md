# AI-Lab Project Status

**Date:** 2026-07-19
**Version:** v0.33.0
**Status:** SP-014 archived; ACC-014 passed; SP-015 not started

## Current Status

SP-014 Unified Inbox 状态为 **APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED**。PR #32 以 Squash Commit `5bad5d412f9f2dabb158527a96c20c6e95e86d6e` 合入；SP-014B 状态为 **APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED**，PR #33 以 Squash Commit `22f85db16a43e7d09a903859a26ac6a310370d81` 合入。ACC-014 A～L 全部 PASSED，结论为 **PASSED / FINAL**。

当前 canonical main 为 `22f85db16a43e7d09a903859a26ac6a310370d81`，产品版本保持 `0.33.0`。合并后 GitHub Quality Gate run `29690136483` 为 SUCCESS：`1154 passed, 6 skipped, 27 warnings`，Ruff 与 pytest (non-real) 均成功。SP-015 仅为 **UNBLOCKED_FOR_PLANNING / NOT_STARTED**。

SP-013 Daily Agenda 最终状态为 **APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED**。Feature merge 为 `67c5ea922a1a6bd935a3c7c31e43fd83e3d32aa1`，post-merge reconciliation 为 `1b4285efa483e5a389cd0055f3e053ccc7a6f25e`，SP-013B CLI workspace 修复通过 PR #29 以 Squash Commit `23b54be4bd3030c564c2e1a0325eaf36199357fe` 进入 `main`。A～H 隔离 Mock 验收均为 PASSED；SP-012 查询兼容性由场景 H 覆盖。

CI-001 已通过 PR #30 以 Squash Commit `7750b1ebd2cc6f937496c904bf1d482952b1b52c` 合并。GitHub Quality Gate 使用 Python 3.12，覆盖 Pull Request、`main` push 与 `workflow_dispatch`；Ruff 是变更 Python 文件增量门禁，pytest 显式排除 `tests/real`。CI-001 建立时的 Ubuntu 基线为 `1096 passed, 6 skipped, 27 warnings`；当前 main 结果见上文 run `29690136483`。

SP-011 Reminder Management and Inbox Experience Closure 已通过 PR #23 以 Squash Commit `5c4b442b2b5c7f934ac381020ba8b310976d5d3a` 合并，状态为 **APPROVED / MERGED / RECONCILED / ARCHIVED**。Composition Root-owned `ReminderManagementService` 已统一详情、取消、改期、workspace 校验、标题歧义与幂等语义，并加入 actionable pending Inbox、确定性响应分离和 CLI UTF-8 边界。RFC-021 已 Adopted，ADR-043/044/045 已 Accepted。

SP-011 手工验收现已记录为：Reminder Core **PASSED**，Natural-language Reminder UX **CONDITIONALLY PASSED**。阻断发现是只读提醒问句可能创建 Work Log 写入。SP-012 为 APPROVED / MERGED / RECONCILED / ARCHIVED；RFC-022 已 Adopted，ADR-046/047/048 已 Accepted。

SP-010 用户验收：**PASSED 7 / 7**；Baseline `0ad1f26ef1712f54f4bf478a70a46e0e50260950`。

SP-010 Reminder Inbox and User-Friendly Local Access 已完成审查并通过 PR #21 以 Squash Merge 进入 `main`，状态为 **APPROVED / MERGED / RECONCILED / ARCHIVED**。Approved Head 为 `2719793102b4318f4b98162f4b288710fe4b44f8`，Merge Commit 为 `af437afc32dcb17da68d600d6840ec94c8cbe681`，合并时间为 `2026-07-16T16:18:28Z`。产品版本保持 `0.33.0`，无新 Tag 或 Release。

项目以 v0.33.0 汇总 SP-001 至 SP-003 的稳定化成果。十一层基础架构 + CEO Assistant 处于 Alpha 状态；Coordination 作为独立层存在，版本唯一来源、Composition Root、失败语义和 DatabaseManager 连接所有权已经收敛。

SP-004 已完成审查并通过 PR #8 以 Squash Merge 合并到 `main`。审查结论为 `APPROVED`，SP-004 merge baseline 为 `10d1534049be2d526c930c513912dc661ac41728`，合并时间为 `2026-07-15T11:39:33Z`。Canonical UserTask、`tasks.db`、真实 Task API、CEO Assistant 接入和 Legacy importer 已进入主分支。

SP-005 已完成审查并通过 PR #10 以 Squash Merge 合并到 `main`。审查结论为 `APPROVED`，SP-005 merge baseline 为 `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`，合并时间为 `2026-07-15T14:03:32Z`。Reminder/Occurrence、Scheduler CAS claim、One-shot terminal、Saga reconciliation 与真实 API 已进入主分支，并保持默认关闭。

当前产品版本仍为 v0.33.0，未创建 v0.34.0 Tag 或 GitHub Release。外部通知渠道、Recurring Reminder、Knowledge Reindex/Chunk Persistence/Citation、自动 Tool Calling、完整 MCP 闭环、Coordination 主链路、UI、Database backup/restore、in-flight counting 与 drain timeout 仍未完成。

## Key Metrics

| Metric | Value |
|---|---|
| Python Files | 493 |
| Code Lines | 35,716 |
| Tests | 当前 GitHub Ubuntu Quality Gate: 1154 passed, 6 skipped, 27 warnings（run 29690136483）；历史 Windows marker-filter baseline: 1102 passed, 5 deselected |
| RFC | 25 files excluding template（RFC-024 Accepted） |
| ADR | 55 files excluding template（ADR-052/053 Accepted） |
| Architecture Layers | 11 |
| Real Provider Validation | DeepSeek 本地验证通过；SentenceTransformer / Chroma 为可选实现，默认未启用 |
| Business Apps | 1 (CEO Assistant) |

## Module Status

| Module | Status | Current Boundary |
|---|---|---|
| Governance | Implemented | 文档与实现仍需持续一致性审查 |
| Core / Database / Memory | Integrated / Verified | 当前稳定化主链路 |
| Provider / Agent Runtime | Integrated / Verified | DeepSeek 本地验证通过；依赖 `real` extra 与授权配置 |
| Knowledge | Implemented / Disabled | Reindex、Chunk Persistence、Citation 与真实主链路未完成 |
| Tool Runtime + MCP | Integrated | Registry/Executor 已接入；自动 Tool Calling 和完整 MCP 产品闭环未完成 |
| Workflow / Task Runtime | Integrated / Verified | 当前组合与失败语义已验证 |
| Scheduler / Reminder | Integrated / Verified / Disabled by default | SP-010 Inbox 已合并；外部通知未实现 |
| Unified Inbox | Integrated / Verified | Capture-to-Action、workspace 隔离、持久化 resolution claim、幂等与崩溃恢复已通过 ACC-014 |
| Coordination | Implemented / Disabled | 默认关闭，未接入 CEO Assistant 主链路 |
| Application Runtime | Integrated / Verified | 只派发注册实例 |
| CEO Assistant | Integrated / Verified / Alpha | CLI 与工作记录闭环可用，尚非生产级产品 |

## Next Milestone

SP-014 与 SP-014B 已完成、对账并封存。SP-015 当前仅为 **UNBLOCKED_FOR_PLANNING / NOT_STARTED**；其任务范围、产品目标和正式任务书必须由 ChatGPT 与 Owner 后续共同确定。

SP-007 已完成并封存：APPROVED / MERGED / RECONCILED / ARCHIVED。PR #14 的 Approved Head 为 `527ecba0ee411edb260b5bbcfdfc24dfa22a5bb4`，Squash Merge Commit 为 `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`，合并时间为 `2026-07-16T10:08:47Z`。它只覆盖 FastAPI 受保护业务路由的生命周期准入；直接 ApplicationRuntime、CEO Assistant 与 CLI 调用仍明确排除。

SP-008 Internal Work Admission Boundary 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #16 的 Approved Head 为 `536d1563baaecf5d50eeefc93dfdb0dbbfe3c659`，Squash Commit 为 `1858d4991379058948559cc96e2672df44e42b67`，合并时间为 `2026-07-16T11:06:29Z`。ApplicationRuntime、CEO Assistant、CLI 业务路径与 Scheduler producer 已共享生命周期准入边界。

SP-009 Natural-Language Reminder Closure with In-App Status 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #19 的 Approved Head 为 `42697e2787d9d9e33f4a7b40c3dd0ea092dcf742`，Squash Commit 为 `b1274d066cbc01053144cba8d5654a5f8c8a21da`，合并时间为 `2026-07-16T13:54:55Z`。受支持的今天/明天提醒、真实持久化调度、唯一 Occurrence 与 API/CLI 站内状态查询已进入 main。

SP-010 Reminder Inbox 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #21 的 Approved Head 为 `2719793102b4318f4b98162f4b288710fe4b44f8`，Squash Commit 为 `af437afc32dcb17da68d600d6840ec94c8cbe681`，合并时间为 `2026-07-16T16:18:28Z`。实现已合并，用户验收 PASSED 7 / 7。

### SP-006: Application API Security Boundary
- 2026-07-15: Integrated / Verified, Merged PR #12
- Bearer-token auth and CORS allowlist implemented; merged
- Merged

> SP-007 System Lifecycle Admission Gate: APPROVED / MERGED / RECONCILED / ARCHIVED. SP-008 Internal Work Admission Boundary: APPROVED / MERGED / RECONCILED / ARCHIVED。
