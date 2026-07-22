# SP-016 — Canonical Waiting-For Domain Acceptance

状态：PASSED / FINAL

版本边界：源码版本仍为 `0.34.0`；SP-016 属于 v0.35.0 开发线；本验收不构成 v0.35.0 发布。

## 场景

| 场景 | 自动化 | 人工验收 | 最终状态 |
|---|---|---|---|
| A — Create / Get / List | PASSED | PASSED | PASSED |
| B — Restart Persistence | PASSED | PASSED | PASSED |
| C — Workspace Isolation | PASSED | PASSED | PASSED |
| D — Optimistic Concurrency | PASSED | PASSED | PASSED |
| E — Follow-up / Snooze History | PASSED | PASSED | PASSED |
| F — Terminal Lifecycle | PASSED | PASSED | PASSED |
| G — Default Agenda Availability | PASSED | PASSED | PASSED |
| H — Agenda Waiting Mapping | PASSED | PASSED | PASSED |
| I — API / CLI Composition Root | PASSED | PASSED | PASSED |
| J — Failure Integrity | PASSED | PASSED | PASSED |

## 稳定验收摘要

验收入口：真实 CLI 子进程与真实 Uvicorn API 进程。

数据边界：全新临时数据目录，CLI/API 共用同一个 `followups.db`。

Provider：mock，无真实外部 Provider 请求。

结果：10 / 10 场景通过。

## 验收驱动说明

验收过程中出现三次非产品驱动问题：PowerShell 尾部断言语法错误、产品命令执行前的驱动解析错误、argparse 换行导致的断言误判。

这些问题未修改产品代码、未删除或重置验收数据，也未改变任何产品命令的真实结果，因此不记录为产品缺陷。

## 独立审查修正证据

- H 保持 `AUTOMATED_VERIFICATION_PASSED`：TODAY/NEXT 分别检查
  `next_review_at` 与 `expected_by`；终态只映射到 COMPLETED；派生状态优先级稳定，
  同一 Waiting-For 只产生一个 AgendaItem。
- I 保持 `AUTOMATED_VERIFICATION_PASSED`：真实 API 与 CLI Composition Root
  接受显式 Waiting-For ID；重复提交返回 conflict，并且只保留一个快照和一个
  `created` 事件。
- J 保持 `AUTOMATED_VERIFICATION_PASSED`：Repository 的 create/mutate 在所有权
  迁移前拒绝 snapshot、event、request 的 workspace 不一致，且不产生部分行或历史变化。
- CLI 证据同时覆盖 snooze 必填时间、正整数 revision，以及纯文本 list/history
  的完整身份字段。
