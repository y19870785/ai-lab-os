# ADR-061 — Daily Review as a Non-persistent Read Model

Status: Proposed / Planning Baseline
Date: 2026-07-26
Target: SP-019

## 背景（Context）

AI-Lab OS 已有 Work Log、UserTask、Reminder、Waiting-For 与 Inbox canonical domains，也有回答未来行动问题的 Daily Agenda。用户需要的是指定 today/yesterday 本地日历日的可追溯事实与生成时未闭环事项，而不是新的持久化业务实体。

现有 CEO Assistant `_handle_brief()` 是直接读取多个来源的旧式 handler；继续扩展会形成第二套聚合真相。把 Daily Agenda 当数据源又会混淆“接下来做什么”和“发生了什么”的语义。

## 决策（Decision）

Daily Review 定义为按需生成、非持久化、deterministic read model：

```text
DailyReviewService
  -> canonical services
  -> deterministic classification
  -> structured DailyReview
```

它不是新 canonical domain。它不拥有数据库、表、事件、生命周期或持久化 snapshot。

`DailyReviewService` 只能直接读取 `WorkLogService`、`WaitingForService`、`ReminderInboxService`、`InboxService` 与 `UserTaskService`。它不能读取 Daily Agenda 的聚合结果，不能绕过 Service 直读数据库，也不能扫描 MemoryManager。

today/yesterday 使用系统 IANA timezone、注入 Clock 和本地午夜半开区间。日期事实由 `review_date` 控制；当前未闭环视图，包括 `pending_inbox`，由 `as_of` 控制。

旧 brief READ intent 与兼容 handler 最终委托同一 `DailyReviewService`。Decision Memory 不进入首版。

## 影响（Consequences）

- 相同 Workspace、Clock 与 source snapshot 得到相同结构化结果。
- API 与 CEO Assistant 可共享事实、reason code、排序及 FailureInfo。
- 没有 Review migration、write-back、event 或 restart recovery 负担。
- 首版不能声称重建任意历史日期的完整 end-of-day 状态。
- UserTask 完整 Workspace query 下推是聚合前必须完成的 Phase 0。

## 被拒绝的替代方案（Rejected Alternatives）

- 持久化 Daily Review snapshot：扩大 Schema 与生命周期，且伪装当前缺失的历史重建能力。
- 扩展 `_handle_brief()`：保留第二套聚合器与不一致合同。
- 复用 Daily Agenda 输出：语义不同且丢失来源级可用性与日期事实。
- 用 LLM 生成事实或 Follow-up：不可解释、不可复现。

## 治理状态（Governance）

本 ADR 仅建立 Planning Baseline。状态为 Proposed，不批准或启动 SP-019 实施。
