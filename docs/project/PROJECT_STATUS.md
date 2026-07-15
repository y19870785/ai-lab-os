# AI-Lab Project Status

**Date:** 2026-07-15
**Version:** v0.33.0
**Status:** Architecture stabilization baseline

## Current Status

项目以 v0.33.0 汇总 SP-001 至 SP-003 的稳定化成果。十层基础架构 + CEO Assistant 处于 Alpha 状态；版本唯一来源、Composition Root、失败语义和 DatabaseManager 连接所有权已经收敛。

SP-004 已完成审查并通过 PR #8 以 Squash Merge 合并到 `main`。审查结论为 `APPROVED`，SP-004 merge baseline 为 `10d1534049be2d526c930c513912dc661ac41728`，合并时间为 `2026-07-15T11:39:33Z`。Canonical UserTask、`tasks.db`、真实 Task API、CEO Assistant 接入和 Legacy importer 已进入主分支。

当前产品版本仍为 v0.33.0，未创建 v0.34.0 Tag 或 GitHub Release。SP-005 Reminder/Occurrence、Scheduler CAS claim、One-shot terminal、Saga reconciliation 与 API 已形成未合并候选；通知渠道、Recurring Reminder、Knowledge Reindex/Chunk Persistence/Citation、自动 Tool Calling、完整 MCP 闭环、Coordination 主链路、UI、Database backup/restore 与 shutdown 全局请求闸门仍未完成。

## Key Metrics

| Metric | Value |
|---|---|
| Python Files | 446 |
| Code Lines | 29,259 |
| Tests | 874 passed, 27 warnings in 52.02s（SP-005 候选 Windows 本地验证，非跨平台 CI） |
| RFC | 16 |
| ADR | 34 |
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
| Scheduler / Reminder | Implementation candidate / Disabled by default | SP-005 候选待审查；外部通知未实现 |
| Coordination | Implemented / Disabled | 默认关闭，未接入 CEO Assistant 主链路 |
| Application Runtime | Integrated / Verified | 只派发注册实例 |
| CEO Assistant | Integrated / Verified / Alpha | CLI 与工作记录闭环可用，尚非生产级产品 |

## Next Milestone

当前稳定化工作是 **SP-005 — Reminder & Scheduler Bridge** 的真实 Diff 审查；审查合并前不扩展通知渠道。
