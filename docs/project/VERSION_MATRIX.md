# 版本兼容性矩阵

**Source Version:** `0.34.0` Alpha Candidate
**Verification:** Verified / Unpublished / Ready for Release Authorization
**Previous Tag:** `v0.33.0`
**v0.34.0 Tag / GitHub Release:** 未创建

## Current capability baseline

| Capability | Governance contract | v0.34.0 source state |
|---|---|---|
| Canonical UserTask | SP-004 | Integrated / Verified |
| Reminder / Scheduler Bridge | SP-005、SP-009～SP-011 | Integrated / Verified / Disabled by default |
| API Security Boundary | SP-006 | Integrated / Verified |
| Lifecycle Admission | SP-007、SP-008 | Integrated / Verified |
| Intent Safety | RFC-022 / ADR-046～048 | Integrated / Verified |
| Daily Agenda | RFC-023 / ADR-049～051 | Integrated / Verified / Manual acceptance passed |
| Unified Inbox / Capture-to-Action | RFC-024 / ADR-052～053 | Integrated / Verified / ACC-014 passed |
| Chinese numeral reminder hours | SP-014B | Integrated / Verified within documented deterministic scope |

## Compatibility boundary

v0.34.0 是从 v0.33.0 源码基线推进的治理与能力汇总，不引入数据库 schema 迁移，也不改变默认启用策略。既有 API、CLI 与 CEO Assistant 继续复用 Composition Root 和 canonical services。

Reminder 中文小时仅支持今天/明天、明确上午/下午/晚上及一至十二小时，可复用既有半、一刻和数字分钟能力。复杂日期、模糊或相对时间、中文分钟、Recurring Reminder 与 LLM 时间解析不在范围内。

## Runtime modules

| Module | Internal contract version | Minimum historical baseline |
|---|---:|---|
| Core / Database / Memory | 1.0 | v0.13.0 |
| Provider / Knowledge | 1.0 | v0.15.0 / v0.16.0 |
| Agent / Tool / MCP | 1.0 | v0.17.0～v0.19.0 |
| Workflow / Scheduler / Task | 1.0 | v0.20.0～v0.22.0 |
| UserTask / Reminder / Agenda / Unified Inbox | 1.0 | v0.34.0 source candidate |

发布状态不是从本表推导；以 `project_state.json` 的 `release_status` 为准。
