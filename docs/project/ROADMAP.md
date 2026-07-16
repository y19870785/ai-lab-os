# AI-Lab Roadmap

**Last Updated:** 2026-07-16 | **Current Version:** v0.33.0

## Completed

| Phase | Version | Date | Deliverable |
|---|---|---|---|
| 1.0-1.6 | v0.1.0 ~ v0.6.1 | 2026-07-11~12 | Foundation: Core + Memory + Governance Architecture |
| 2.0-2.7 | v0.7.0 ~ v0.14.0 | 2026-07-12 | Core & Memory Implementation + Stabilization |
| 3.0-3.4 | v0.15.0 ~ v0.19.0 | 2026-07-12 | Provider、Knowledge、Agent、Tool、MCP 基础实现；部分能力默认 Disabled |
| 4.0-4.3 | v0.20.0 ~ v0.23.0 | 2026-07-12~13 | Workflow/Task 已接入；Scheduler/Coordination Runtime 已实现但默认 Disabled |
| 5.0-5.1 | v0.30.0 ~ v0.31.0 | 2026-07-13 | Application Foundation + Alpha Field Validation |
| Product 1.0-1.2 | v0.32.0 ~ v0.32.4 | 2026-07-13~14 | CEO Assistant MVP + DeepSeek + Interactive CLI |
| Stabilization | v0.33.0 | 2026-07-15 | SP-001~SP-003 Composition Root、失败语义、数据库连接所有权与版本治理 |
| SP-004 | v0.33.0（未新增 Release） | 2026-07-15 | Canonical UserTask、`tasks.db`、真实 Task API、CEO Assistant 接入与 Legacy importer |
| SP-005 | Unreleased（post-v0.33.0 main） | 2026-07-15 | Reminder/Occurrence、Scheduler CAS claim、Action Handler 与 Saga reconciliation；PR #10 已合并，默认关闭 |

## Current

| Status | Action |
|---|---|
| **BASELINE** | post-v0.33.0 main — SR-001 assessment baseline `51fd6b38417840044f6ee1a1a699d13186762017` |
| **CURRENT** | SP-009 implementation candidate / Draft PR / Awaiting ChatGPT review / Not merged |
| **LIMITS** | 通知渠道、Recurring Reminder、Knowledge 主链路、自动 Tool Calling、完整 MCP 闭环、Coordination 主链路和 UI 仍未完成 |

## Future (Tentative)

| Version | Goal |
|---|---|
| v0.33.0 | 根据审查结果修复关键问题（P1 技术债清理） |
| v0.34.0 | 目标里程碑：CEO Assistant 产品化完善（Tag / Release 尚未创建） |
| v0.40.0 | Beta Release — 多 App 支持 |
| v0.50.0 | 企业微信 / ERP / 报价系统接入 |
| v1.0.0 | Production Release — 稳定运营 |

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 与 SP-008 均已 APPROVED / MERGED / RECONCILED / ARCHIVED。SR-001 选择 Natural-Language Reminder Closure 为首个可验收产品切片；SP-009 仅为候选，尚未合并。
