# SP-020 产品实施任务书

## 任务

**SP-020 — Local Daily Operating Loop & Review-to-Action Closure**

中文：**本地日常运行与复盘行动闭环**

```text
Planning Base SHA:
934075ceefe39ede3c624b621b7673d62f6d06dd

Planning Branch:
docs/sp-020-local-daily-operating-loop-planning

Planning PR:
#53 (Draft)

Suggested Future Implementation Branch:
feat/sp-020-local-daily-operating-loop

Planning Status:
PLANNING_BASELINE_APPROVED / MERGED / RECONCILED

Implementation:
NOT APPROVED / NOT STARTED
```

本任务书定义未来授权边界，不是实施授权。任何 Phase 都必须等待 Planning PR 独立审查、
合并以及 Owner 的新一轮明确授权。

## 范围

- Windows Local Daily Profile：稳定绝对 data/sqlite root、显式 IANA timezone、
  Provider mode、feature flags、API auth 与 localhost bind。
- 启动配置安全展示、health/readiness 与优雅 shutdown。
- Scheduler shutdown 幂等、partial-start rollback 与 restart recovery 门禁。
- 直接调用现有 `DailyReviewService` 的正式 `daily-review` CLI。
- 纯确定性、无 LLM、无写入的 Action Hint presentation。
- Review canonical ID 到现有 UserTask、Reminder、Waiting-For、Inbox 与 Work Log
  服务的显式委托闭环。
- 真实 Windows 进程、SQLite、重启、静止备份与隔离恢复的 ACC-020。

## 非目标

Recurring Reminder、外部通知、邮件/短信/企业微信/手机推送、Web UI、新
Project/Goal/Outcome 领域、Knowledge 主链路、Agent 自动规划/Tool Calling、MCP 自动
执行、用户身份、OAuth/JWT/RBAC、强多租户、任意历史 Review、Review Snapshot、LLM
自动建议并执行、在线跨库一致快照、集群/高可用、复杂编排、大型 migration、全仓
重构、Plugin framework、Command Bus 重写、大规模 CEO Assistant 重构，以及新增
Work Log edit/complete/delete。

## 架构边界

1. `core/system/factory.py:create_system()` 与 `SystemContainer` 是唯一 Composition
   Root。
2. 所有入口使用同一个 container 中的 canonical services，不组装第二套 repository。
3. `DailyReviewService` 继续无数据库、无事件、无 persistence、无 LLM、无写入、无
   独立 lifecycle。
4. Action Hint 只描述真实 allowed action；Action Execution 必须由 canonical domain
   service 完成。
   `available_entrypoints` 只列出当前真实存在且安全的入口；一个 action 至少有一个
   真实安全入口即可展示，不要求 API、CLI、CEO Assistant 三者同时存在。
5. 完整 `WorkspaceKey` 在 API、CLI、CEO Assistant、Review、hint 与 mutation 之间
   一致传递。
6. revision、idempotency、preview/confirm、Inbox durable claim/Saga 必须按动作分别
   声明并遵守，不能被绕过。UserTask update 当前接受调用方 `expected_revision`；
   complete/cancel 当前只使用 Service 读取到的最新 revision，API 与 Service 不接受
   调用方 revision。SP-020 未来实现必须为 Review-to-Action 的 UserTask
   complete/cancel 增加显式 `expected_revision`。
7. Work Log 仍只有 create/get/list。
8. 默认备份为停机后的完整 data directory 复制；不承诺在线跨库一致快照。

## 实施阶段

SP-020 产品实施需要一次明确的 Owner 授权。Phase 0 是同一次实施授权内部的强制质量
门禁；通过 Phase 0 后不需要再次请求 Owner 授权。若 Phase 0 失败、触发停止条件、需要
改变已批准范围、拆分 Product SP 或引入新的架构决策，必须立即停止并重新请求 Owner
决策。本 Planning Baseline 尚未授予该实施授权。

### 阶段 0 — 产品入口与生命周期门禁

只处理阻碍真实使用的入口与生命周期基础问题：

- Local Daily Profile 与稳定绝对数据目录；
- 完整 WorkspaceKey CLI 传递；
- 非敏感最终配置展示与稳定配置失败；
- API health/readiness/shutdown；
- partial startup rollback；
- 重复 shutdown 与当前双 Scheduler shutdown 调用的幂等证明；
- Scheduler/Reminder/Inbox Saga/Waiting-For 新进程恢复；
- 多个 Scheduler tick、一次真实 one-shot job、空闲运行窗口、周期性 health 快照、
  background task 状态与 DatabaseManager connection count 的持续运行证据；
- 防止数据目录调整静默遗弃旧数据。

Phase 0 未通过不得进入 Phase 1。

### 阶段 1 — 每日回顾 CLI

仅实现：

```powershell
python -m cli daily-review --date today
python -m cli daily-review --date yesterday
python -m cli daily-review --date today --json
```

必须直接复用现有 `DailyReviewService.query_from_input()`、`get()` 与纯 Presenter。

### 阶段 2 — 确定性操作提示

只实现 ADR-063 的纯 presentation model。不得执行、持久化、调用 LLM 或新增 Action
数据库。

### 阶段 3 — 回顾到操作入口闭环

只补齐 ACC-020 日常用户闭环实际需要的薄入口委托。不得为了入口对称性补齐所有领域
动作，不追求 API、CLI、CEO Assistant 的完整矩阵对称，不得复制领域 mutation、
建立第二 Command Bus 或为 Work Log 发明新 mutation。

### 阶段 4 — 持续每日验收

冻结 Approved Implementation Head 后，使用真实 Windows 进程与真实 SQLite 执行
ACC-020；验收使用 mock/test Provider，Provider calls 必须为 0。

## 停止条件

- main 不再等于授权 Base，或存在未处理 Product PR；
- 需要两个以上独立 Product SP；
- 需要修改多个领域 schema、migration、Action/Review 数据库或 snapshot；
- 需要 LLM 选择对象、动作或写入内容；
- 需要绕过 WorkspaceKey、revision、idempotency、confirmation 或 Inbox Saga；
- 需要 DailyReviewService / Presenter 写入；
- 需要第二套 Command Bus 或大规模 CEO Assistant 重构；
- 需要新增 Work Log mutation；
- Scheduler restart 出现重复执行、丢失 job 或状态漂移；
- Scheduler shutdown 幂等无法证明；
- 数据目录变更可能静默丢弃旧数据；
- 恢复需要在线跨库事务或一致快照；
- Windows 无法稳定启动、停止和恢复。

触发后只提交审计证据或 Blocking Finding，不得扩大实现。

## 必需测试

每个实现 Phase 必须执行与变更风险相称的定向测试，并至少执行：

```powershell
python -m pytest tests/governance -q
python -m pytest tests/core/test_version.py -q
python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no
python -m pytest tests -q --tb=no
python -m ruff check <changed-python-files>
python -m build
git diff --check
```

不得删除测试、扩大 skip/xfail、放宽断言或用 product change 掩盖验收 driver/harness
错误。真实 Provider 测试不属于普通门禁。

## ACC-020 验收

正式验收定义见
`docs/acceptance/SP-020-local-daily-operating-loop.md`。所有场景当前均为
`PLANNING_BASELINE / NOT_EXECUTED`。Planning merge 不等于执行 ACC-020。

## 发布边界

```text
Current Product Version:
0.34.0 / UNCHANGED

Target Version:
0.35.0 candidate only

Version change:
NOT AUTHORIZED

Tag:
NOT AUTHORIZED / UNCHANGED

GitHub Release:
NOT AUTHORIZED / UNCHANGED
```

## 治理状态

```text
SP-020 Planning Baseline:
DEFINED / PENDING INDEPENDENT REVIEW

SP-020 Implementation:
NOT APPROVED / NOT STARTED

ACC-020:
PLANNING_BASELINE / NOT_EXECUTED
```
