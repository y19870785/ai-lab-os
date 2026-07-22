# SP-016 — Canonical Waiting-For Domain Acceptance

状态：AUTOMATED VERIFICATION PASSED / MANUAL ACCEPTANCE PENDING

版本边界：源码仍为 `0.34.0`；SP-016 面向 v0.35.0 开发线，但尚未完成人工验收、合并后对账或版本发布。

## 场景

| 场景 | 自动化证明 | 当前状态 |
|---|---|---|
| A — Create / Get / List | revision=1、created sequence=1、open list | AUTOMATED_VERIFICATION_PASSED |
| B — Restart Persistence | 同一 data dir 重启后快照与事件恢复 | AUTOMATED_VERIFICATION_PASSED |
| C — Workspace Isolation | 跨 workspace get/list 隔离且安全 not-found | AUTOMATED_VERIFICATION_PASSED |
| D — Optimistic Concurrency | 同 revision 仅首个 CAS 成功且只追加一个事件 | AUTOMATED_VERIFICATION_PASSED |
| E — Follow-up / Snooze History | 连续 append-only event 与 next_review_at 更新 | AUTOMATED_VERIFICATION_PASSED |
| F — Terminal Lifecycle | resolve、终态拒绝、reopen、cancel 一致 | AUTOMATED_VERIFICATION_PASSED |
| G — Default Agenda Availability | Reminder/Scheduler 关闭时 Agenda 仍存在 | AUTOMATED_VERIFICATION_PASSED |
| H — Agenda Waiting Mapping | future/action、due/attention、terminal/completed 且无重复 | AUTOMATED_VERIFICATION_PASSED |
| I — API / CLI Composition Root | API lifespan 与 CLI create_system 使用 canonical Service | AUTOMATED_VERIFICATION_PASSED |
| J — Failure Integrity | transaction/event/CAS/init failure 无假成功或部分状态 | AUTOMATED_VERIFICATION_PASSED |

## 人工验收边界

上述结论只代表自动化验证通过。人工验收尚未执行，不得将 SP-016 标记为 completed、reconciled 或 archived，也不得据此启动 SP-017。

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
