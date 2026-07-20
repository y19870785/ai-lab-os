# AI-Lab Project Status

**Date:** 2026-07-20
**Source Version:** v0.34.0 Alpha Candidate
**Canonical main baseline:** `01166352224ddce5e859d4133f502aee1f97da07`

## Current governance state

| Item | State |
|---|---|
| SP-014 | APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-014B | APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED |
| ACC-014 | PASSED / FINAL（A～L 全部通过） |
| SP-015 | APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-015A | IN_PROGRESS / DRAFT_PR_OPEN |
| SP-016 | Follow-up & Waiting-For Workflow / CANDIDATE / NOT_APPROVED / NOT_STARTED |

根目录 `project_state.json` 是唯一机器可读实时项目状态源；本页是便于人工阅读的摘要。运行时产品版本仍只来自 `pyproject.toml`。

## Product baseline

v0.34.0 Alpha Candidate 汇总 Canonical UserTask、Reminder、Intent Safety、Daily Agenda、Unified Inbox 与 Capture-to-Action。Reminder 和 Scheduler 能力已集成并验证，但默认关闭；Knowledge 和 Coordination 仍不是默认主链路。

SP-014 通过 PR #32 合并，SP-014B 通过 PR #33 合并，最终治理对账通过 PR #34 合并。ACC-014 的场景 A～L 均为 PASSED，场景 K 的中文小时兼容缺口已由 SP-014B 修复并在 main 复验。

## Quality baseline

当前 main 的正式 GitHub Quality Gate 为 run `29738408215`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1162 passed, 6 skipped, 27 warnings`。SP-015 post-merge acceptance A～I 已通过。真实 Provider 测试不属于普通门禁。

## Release state

- 源码版本：`0.34.0`
- 成熟度：Alpha / local-first / single-user-oriented
- 上一 Tag：`v0.33.0`
- v0.34.0 Tag：未创建
- v0.34.0 GitHub Release：未创建
- 发布阻断：SP-015A 合并、SP-015A main Quality Gate、Owner 与 ChatGPT 的独立发布授权

SP-015 已合并、通过 post-merge acceptance 并封存，未修改业务语义或数据库 schema。SP-015A 正在 Draft PR 中执行 release reconciliation；SP-016 Follow-up & Waiting-For Workflow 仅为候选，不得由本状态自动批准或启动。
