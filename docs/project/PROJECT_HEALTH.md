# AI-Lab Project Health

**Last Updated:** 2026-07-17
**Current Version:** v0.33.0

## Summary

> SP-011 已通过 PR #23 合并并完成治理对账，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。管理协调、pending Inbox、确定性响应与 CLI UTF-8 已进入 main；手工产品验收待执行。SP-010 用户验收为 PASSED 7 / 7，Baseline `0ad1f26ef1712f54f4bf478a70a46e0e50260950`。

| Metric | Value |
|---|---|
| Version | v0.33.0 |
| SP-011 pre-merge tests | 1026 passed, 27 warnings in 58.15s（Windows 本地 Python 3.12；非 GitHub Actions 或跨平台 CI） |
| RFCs | 23（RFC-021 已 Adopted） |
| ADRs | 48（ADR-043/044/045 已 Accepted） |
| Tests | 1026（SP-011 合并前 Windows 本地验证记录） |
| Test Pass Rate | 100% (1026 passed, 0 failed, 0 errors；非跨平台 CI 结果) |
| Real Provider Tests | 5 passed in 8.37s in a fresh isolated Python 3.12 environment |
| Technical Debt (Open) | 7 |
| Technical Debt (Resolved) | 1 (TD-001 documented) |
| Release Stage | Alpha |
| Development Status | **Architecture stabilization baseline** |

## Architecture Status

| Module | Status | Evidence / Limitation |
|---|---|---|
| Governance | Implemented | RFC、ADR 与策略文档存在，持续核对实现一致性 |
| Core / Database / Memory | Integrated / Verified | Composition Root、失败语义、连接所有权与持久化测试覆盖 |
| Provider / Agent / Workflow / Task | Integrated / Verified | Mock 与真实 LLM 路径、运行时和失败语义已验证 |
| UserTask | Integrated / Verified | SP-004 已合并；正式领域、`tasks.db`、真实 API、CEO Assistant 接入和 Legacy importer 已验证 |
| Knowledge | Implemented / Disabled | 默认不启动；Reindex、Chunk Persistence、Citation 和真实主链路未完成 |
| Tool Runtime / MCP | Integrated | Registry/Executor 和低风险工具已接入；自动 Tool Calling 与完整 MCP 产品闭环未完成 |
| Scheduler / Reminder | Integrated / Verified / Disabled by default | Inbox、CAS claim、Occurrence 幂等与 Saga 已合并；通知渠道未实现 |
| Coordination | Implemented / Disabled | 默认关闭；CEO Assistant 主链路未接入 |
| Application / CEO Assistant | Integrated / Verified / Alpha | CLI、API 工作记录和持久化已验证；尚非生产级产品 |

## SP-011 Verification Record

以下均为合并前 Windows 本地 Python 3.12 验证记录，不是 GitHub Actions 或跨平台持续 CI 保证：

- Full local tests: 1026 passed, 27 warnings, 0 failed, 0 errors
- Reminder Core: 24 passed
- API: 91 passed, 1 warning
- CLI: 18 passed
- CEO Assistant: 66 passed
- Integration: 113 passed, 1 warning
- compileall: PASS
- API startup smoke: PASS
- CLI startup smoke: PASS
- Windows subprocess UTF-8 capture: PASS
- Cancellation occurrence test: PASS
- Reschedule restart/effectively-once test: PASS
- Workspace and ambiguity tests: PASS
- Deterministic response separation tests: PASS

## Freeze Info

- Freeze Date: 2026-07-14
- Freeze Reason: Independent GPT-5.6 architecture review
- Historical Tag: `v0.32.4-review-baseline`（保留，不重写）
- SP-004: Completed / Merged / Archived
- SP-004 Merge PR: #8（Squash Merge / APPROVED）
- SP-004 Merge Baseline: `10d1534049be2d526c930c513912dc661ac41728`
- SP-004 Merged At: `2026-07-15T11:39:33Z`
- UserTask: Integrated / Verified
- SP-005: Completed / Merged / Archived
- SP-005 Merge PR: #10（Squash Merge / APPROVED）
- SP-005 Merge Baseline: `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`
- SP-005 Merged At: `2026-07-15T14:03:32Z`
- Current Work: 无；SP-011 已 APPROVED / MERGED / RECONCILED / ARCHIVED，手工产品验收待执行，下一任务尚未选择
- Validation Source: SP-005 为 Windows 本地 `888 passed, 27 warnings in 45.19s`，不是 GitHub Actions 或跨平台 CI 结果

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 System Lifecycle Admission Gate 与 SP-008 Internal Work Admission Boundary 均已 APPROVED / MERGED / RECONCILED / ARCHIVED。SP-008 通过 PR #16 以 Squash Commit `1858d4991379058948559cc96e2672df44e42b67` 进入 main。`977 passed, 27 warnings, 0 failed, 0 errors` 是 Windows 本地 Python 3.12 历史合并验证，不是 GitHub Actions 或跨平台 CI 保证。

> SP-009 合并前验证：Windows 本地 Python 3.12 `1006 passed, 27 warnings, 0 failed, 0 errors`；不是 GitHub Actions 或跨平台 CI 保证。API startup smoke、CLI persisted status smoke、restart persistence 与 occurrence effectively-once 均为 PASS。

> SP-010 合并前验证：Reminder `18 passed`；API `86 passed, 1 warning`；CLI `17 passed`；CEO Assistant `66 passed`；Integration `112 passed, 1 warning`；compileall、workspace 隔离、只读自然语言查询与 PowerShell 5.1 UTF-8 smoke 均为 PASS。完整本地结果为 `1013 passed, 27 warnings, 0 failed, 0 errors`，不是 GitHub Actions 或跨平台 CI 保证。

> Open limits：无进程级 in-flight counter、drain timeout、强制取消或分布式/多进程 admission coordination。外部通知、Recurring Reminder、复杂日期解析与 Web UI 仍未实现；跨 SQLite Inbox 聚合不是快照事务，深度稀疏过滤仍是性能观察点。
