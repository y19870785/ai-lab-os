# ADR-030：Canonical UserTask Domain

## 状态

Accepted / Implemented

## 采用记录

SP-004 已通过 PR #8 完成审查，审查结论为 `APPROVED`，并于 `2026-07-15T11:39:33Z` 以 Squash Merge 合并到 `main`。SP-004 merge baseline 为 `10d1534049be2d526c930c513912dc661ac41728`。

## 决策

建立独立 `core/user_tasks` 作为唯一用户待办领域。UserTask 不复用 Workflow 的 Execution Task，也不继续把 Decision Memory 当作正式任务数据库。数据持久化到统一 SQLite 目录的 `tasks.db`，连接由 DatabaseManager 所有。

历史 `type=task` Decision Memory 通过显式、分页、幂等、非破坏 importer 兼容；deadline、priority、status、session、agent 和 source 按明确规则迁移。终态时间只在旧记录提供真实 `completed_at`/`cancelled_at` 时迁移，缺失时保留未知，不使用创建时间替代。`due_at` 统一存储 UTC，`timezone` 使用有效 IANA 标识；列表查询时间同样在 Service 的领域校验边界内规范化。Reminder 与 Scheduler 桥梁留给 SP-005。

## 原因

用户待办、工作流执行任务和定时作业具有不同生命周期、失败语义和查询需求。继续共用模型会污染边界；继续写 Decision Memory 会让查询、状态转换、并发更新和 API 真实性无法保证。

## 后果

API 和 CEO Assistant 统一依赖 UserTaskService。更新使用 `revision >= 1` 防止静默覆盖；旧任务不会自动无限双读，也不会被删除。损坏持久化行统一报告 Persistence Failure。系统新增一个由 Composition Root 管理的 `user_tasks` 关键组件。
