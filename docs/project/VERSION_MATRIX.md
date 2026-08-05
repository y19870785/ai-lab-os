# 版本兼容性矩阵

**源码版本：** `0.35.0` Alpha / GitHub Pre-release Published
**治理状态：** REL-035 / FINAL_RECONCILED / ARCHIVED
**当前治理任务：** None
**下一规划治理项：** ARCH-001 / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION
**已发布 Tag：** `v0.35.0`；上一已发布 Tag：`v0.34.0`
**当前发布：** `v0.35.0 Alpha — Local Daily Operating Loop` / PRE_RELEASE_PUBLISHED

## 当前能力基线

| 能力 | 治理合同 | v0.35.0 源码状态 |
|---|---|---|
| Canonical UserTask | SP-004 | Integrated / Verified |
| Reminder / Scheduler Bridge | SP-005、SP-009～SP-011 | Integrated / Verified / Disabled by default |
| API Security Boundary | SP-006 | Integrated / Verified |
| Lifecycle Admission | SP-007、SP-008 | Integrated / Verified |
| Intent Safety | RFC-022 / ADR-046～048 | Integrated / Verified |
| Daily Agenda | RFC-023 / ADR-049～051 | Integrated / Verified / Manual acceptance passed |
| Unified Inbox / Capture-to-Action | RFC-024 / ADR-052～053 | Integrated / Verified / ACC-014 passed |
| Chinese numeral reminder hours | SP-014B | Integrated / Verified within documented deterministic scope |

## v0.35.0 已发布 Pre-release 能力基线

本节记录已进入 main 且通过验收、由 v0.35.0 GitHub Pre-release 汇总的能力；
annotated Tag 与 Release 已远端验证，但 Alpha 成熟度和已知限制保持不变。

| 能力 | 治理合同 | 当前 main 状态 |
|---|---|---|
| Canonical Waiting-For Domain | SP-016 | Integrated / Verified / ACC-016 passed |
| Waiting-For interaction / Inbox confirmation | SP-017 | Integrated / Verified / ACC-017 passed |
| Canonical Work Log query boundary | SP-018 | Integrated / Verified / ACC-018 passed |
| Daily Review Read Model | SP-019 | Integrated / Verified / ACC-019 passed |
| Local Daily Profile / Daily Review CLI / Action Hints | SP-020 | Integrated / Verified / ACC-020 passed |
| Review-to-Action / lifecycle / backup-restore | SP-020 | Integrated / Verified / ACC-020 passed |

## v0.36+ 战略兼容边界

STRAT-001 不改变 `0.35.0` 运行时或内部合同版本。后续自然交互通过可替换 Agent Shell、
中立 Adapter Contract 和 Trusted Interaction Boundary 演进；现有 API、CLI、CEO
Assistant 与领域服务保持兼容，任何弃用都需要独立规划。

Hermes 是首个首选但可替换的 Agent Shell。Hermes Memory、Conversation 与 Tool
Response 不分别构成业务事实、审批事实和最终成功证明；Hermes 不得直接访问 AI-Lab
数据库，AI-Lab 不得依赖 Hermes 内部实现。

## 兼容性边界

v0.34.0 是从 v0.33.0 源码基线推进的治理与能力汇总，不引入数据库 schema 迁移，也不改变默认启用策略。既有 API、CLI 与 CEO Assistant 继续复用 Composition Root 和 canonical services。

Reminder 中文小时仅支持今天/明天、明确上午/下午/晚上及一至十二小时，可复用既有半、一刻和数字分钟能力。复杂日期、模糊或相对时间、中文分钟、Recurring Reminder 与 LLM 时间解析不在范围内。

v0.34.0 → v0.35.0 不需要破坏性数据库迁移、既有表重写、legacy import 或 dual-write。
既有 UserTask、Reminder、Inbox 与 Work Log 数据保持原样；若 `followups.db` 不存在，
`waiting_for_items`、`waiting_for_events` 与相关索引由当前代码通过 `IF NOT EXISTS`
增量初始化。旧 `.env` 不保证满足 Local Daily Profile，必须改用稳定绝对 data/sqlite
路径、有效 IANA timezone、显式 Provider/feature flags/API token 和完整 WorkspaceKey。

## 运行时模块

| 模块 | 内部合同版本 | 最低历史基线 |
|---|---:|---|
| Core / Database / Memory | 1.0 | v0.13.0 |
| Provider / Knowledge | 1.0 | v0.15.0 / v0.16.0 |
| Agent / Tool / MCP | 1.0 | v0.17.0～v0.19.0 |
| Workflow / Scheduler / Task | 1.0 | v0.20.0～v0.22.0 |
| UserTask / Reminder / Agenda / Unified Inbox | 1.0 | v0.34.0 Alpha |

稳定发布授权不是从本表推导；以 `project_state.json` 的 `release_status` 为准。Tag 与 GitHub Release 的实际存在性、目标、URL 和时间以 GitHub 为权威来源。
