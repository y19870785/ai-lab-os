# AI-Lab Project Status

**Date:** 2026-07-22
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
| SP-016 | Canonical Waiting-For Domain & Agenda Closure / PLANNING_BASELINE_DEFINED / NOT_APPROVED_FOR_IMPLEMENTATION / NOT_STARTED |
| SP-017～SP-019 | Candidate only / NOT_APPROVED / NOT_STARTED |

根目录 `project_state.json` 是唯一机器可读仓库治理状态与稳定发布授权源；本页是便于人工阅读的摘要。当前 Git/GitHub 对象按需查询，运行时产品版本仍只来自 `pyproject.toml`。

## Product baseline

v0.34.0 Alpha 汇总 Canonical UserTask、Reminder、Intent Safety、Daily Agenda、Unified Inbox 与 Capture-to-Action。Reminder 和 Scheduler 能力已集成并验证，但默认关闭；Knowledge 和 Coordination 仍不是默认主链路。

SP-014 通过 PR #32 合并，SP-014B 通过 PR #33 合并，最终治理对账通过 PR #34 合并。ACC-014 的场景 A～L 均为 PASSED，场景 K 的中文小时兼容缺口已由 SP-014B 修复并在 main 复验。

## Quality baseline

最终发布提交前的已验证 main 基线对应 GitHub Quality Gate run `29855987444`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1163 passed, 6 skipped, 27 warnings`。该 commit 是历史验证基线，不是 tracked 文件对自身当前 commit 的声明。真实 Provider 测试不属于普通门禁。

## Release state

- 源码版本：`0.34.0`
- 成熟度：Alpha / local-first / single-user-oriented
- 发布状态：ALPHA / RELEASE_AUTHORIZED
- 授权 Tag：`v0.34.0`
- GitHub Release 类型：Pre-release
- 二进制附件：不发布 wheel 或 sdist，仅使用 GitHub 自动源码归档
- 外部发布事实：实际 Tag 存在性与目标、Release 发布状态、URL 和时间以 GitHub Tags and GitHub Releases 为权威来源

SP-015、SP-015A 与 SP-015R 均已合并并封存；Current Product SP 与 Current Governance Task 均为 None。SP-016 Canonical Waiting-For Domain & Agenda Closure 的 planning baseline 已定义，但未批准实现、未启动；SP-017～SP-019 仅为候选。本规划不修改业务语义或数据库 schema。
