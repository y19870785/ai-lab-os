# AI-Lab Project Status

**Date:** 2026-07-17
**Version:** v0.33.0
**Status:** Architecture stabilization baseline

## Current Status

SP-011 Reminder Management and Inbox Experience Closure 已通过 PR #23 以 Squash Commit `5c4b442b2b5c7f934ac381020ba8b310976d5d3a` 合并，状态为 **APPROVED / MERGED / RECONCILED / ARCHIVED**。Composition Root-owned `ReminderManagementService` 已统一详情、取消、改期、workspace 校验、标题歧义与幂等语义，并加入 actionable pending Inbox、确定性响应分离和 CLI UTF-8 边界。RFC-021 已 Adopted，ADR-043/044/045 已 Accepted。

SP-011 手工验收现已记录为：Reminder Core **PASSED**，Natural-language Reminder UX **CONDITIONALLY PASSED**。阻断发现是只读提醒问句可能创建 Work Log 写入。SP-012 为 APPROVED / MERGED / RECONCILED / ARCHIVED；RFC-022 与 ADR-046/047/048 均保持 Proposed。

SP-010 用户验收：**PASSED 7 / 7**；Baseline `0ad1f26ef1712f54f4bf478a70a46e0e50260950`。

SP-010 Reminder Inbox and User-Friendly Local Access 已完成审查并通过 PR #21 以 Squash Merge 进入 `main`，状态为 **APPROVED / MERGED / RECONCILED / ARCHIVED**。Approved Head 为 `2719793102b4318f4b98162f4b288710fe4b44f8`，Merge Commit 为 `af437afc32dcb17da68d600d6840ec94c8cbe681`，合并时间为 `2026-07-16T16:18:28Z`。产品版本保持 `0.33.0`，无新 Tag 或 Release。

项目以 v0.33.0 汇总 SP-001 至 SP-003 的稳定化成果。十层基础架构 + CEO Assistant 处于 Alpha 状态；版本唯一来源、Composition Root、失败语义和 DatabaseManager 连接所有权已经收敛。

SP-004 已完成审查并通过 PR #8 以 Squash Merge 合并到 `main`。审查结论为 `APPROVED`，SP-004 merge baseline 为 `10d1534049be2d526c930c513912dc661ac41728`，合并时间为 `2026-07-15T11:39:33Z`。Canonical UserTask、`tasks.db`、真实 Task API、CEO Assistant 接入和 Legacy importer 已进入主分支。

SP-005 已完成审查并通过 PR #10 以 Squash Merge 合并到 `main`。审查结论为 `APPROVED`，SP-005 merge baseline 为 `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`，合并时间为 `2026-07-15T14:03:32Z`。Reminder/Occurrence、Scheduler CAS claim、One-shot terminal、Saga reconciliation 与真实 API 已进入主分支，并保持默认关闭。

当前产品版本仍为 v0.33.0，未创建 v0.34.0 Tag 或 GitHub Release。外部通知渠道、Recurring Reminder、Knowledge Reindex/Chunk Persistence/Citation、自动 Tool Calling、完整 MCP 闭环、Coordination 主链路、UI、Database backup/restore、in-flight counting 与 drain timeout 仍未完成。

## Key Metrics

| Metric | Value |
|---|---|
| Python Files | 456 |
| Code Lines | 29,259 |
| Tests | SP-011 pre-merge validation: 1026 passed, 27 warnings in 58.15s（Windows 本地，非 GitHub Actions 或跨平台 CI） |
| RFC | 23（RFC-021 已 Adopted） |
| ADR | 48（ADR-043/044/045 已 Accepted） |
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
| Coordination | Implemented / Disabled | 默认关闭，未接入 CEO Assistant 主链路 |
| Application Runtime | Integrated / Verified | 只派发注册实例 |
| CEO Assistant | Integrated / Verified / Alpha | CLI 与工作记录闭环可用，尚非生产级产品 |

## Next Milestone

SP-007 已完成并封存：APPROVED / MERGED / RECONCILED / ARCHIVED。PR #14 的 Approved Head 为 `527ecba0ee411edb260b5bbcfdfc24dfa22a5bb4`，Squash Merge Commit 为 `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`，合并时间为 `2026-07-16T10:08:47Z`。它只覆盖 FastAPI 受保护业务路由的生命周期准入；直接 ApplicationRuntime、CEO Assistant 与 CLI 调用仍明确排除。

SP-008 Internal Work Admission Boundary 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #16 的 Approved Head 为 `536d1563baaecf5d50eeefc93dfdb0dbbfe3c659`，Squash Commit 为 `1858d4991379058948559cc96e2672df44e42b67`，合并时间为 `2026-07-16T11:06:29Z`。ApplicationRuntime、CEO Assistant、CLI 业务路径与 Scheduler producer 已共享生命周期准入边界。

SP-009 Natural-Language Reminder Closure with In-App Status 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #19 的 Approved Head 为 `42697e2787d9d9e33f4a7b40c3dd0ea092dcf742`，Squash Commit 为 `b1274d066cbc01053144cba8d5654a5f8c8a21da`，合并时间为 `2026-07-16T13:54:55Z`。受支持的今天/明天提醒、真实持久化调度、唯一 Occurrence 与 API/CLI 站内状态查询已进入 main。

SP-010 Reminder Inbox 已完成并封存：**APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #21 的 Approved Head 为 `2719793102b4318f4b98162f4b288710fe4b44f8`，Squash Commit 为 `af437afc32dcb17da68d600d6840ec94c8cbe681`，合并时间为 `2026-07-16T16:18:28Z`。实现已合并，用户验收 PASSED 7 / 7。

### SP-006: Application API Security Boundary
- 2026-07-15: Integrated / Verified, Merged PR #12
- Bearer-token auth and CORS allowlist implemented; merged
- Merged

> SP-007 System Lifecycle Admission Gate: APPROVED / MERGED / RECONCILED / ARCHIVED. SP-008 Internal Work Admission Boundary: APPROVED / MERGED / RECONCILED / ARCHIVED。
