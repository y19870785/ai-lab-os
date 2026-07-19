# Release Notes —— v0.21.0

> 历史快照：本文件记录 v0.21.0，不表示当前版本或当前 Release 状态。当前 v0.34.0 Alpha Candidate 说明见 [`docs/releases/v0.34.0-alpha.md`](../releases/v0.34.0-alpha.md)，实时状态见根目录 [`project_state.json`](../../project_state.json)。

**发布日期：** 2026-07-13
**版本号：** v0.21.0 Alpha

## 本次发布内容

### Scheduler Runtime（新）

- 统一调度中心，支持 Cron / Interval / One-shot / Manual / Event 五种触发方式
- Tick-loop 调度循环，自动检测到期 Job 并执行
- Job 通过 Workflow Runtime 执行业务（Scheduler 不直接执行业务）
- SQLite 持久化，重启自动恢复
- 并发限制（max_concurrent_jobs）

### 技术指标

- 新增 48 个测试，总计 463 个，零回归
- RFC 12 篇，ADR 23 篇
- 九层架构：Governance + Scheduler + Workflow + Application + Agent + Knowledge + Provider + Memory + Core

## 升级说明

新增 `core/scheduler/` 模块，与现有模块无冲突。

## 已知限制

- Cron 解析仅支持 `*/N` 格式，完整 Cron 解析待 v0.22.0
- Event Trigger 为预留接口，未实现 EventBus 触发
- 单进程调度，不支持分布式
