# ADR-060：显式 Work Log Context Reference

Status: Accepted

> 这是 SP-018 规划基线的 Accepted 架构决策，不批准或启动产品实施。

## 背景

Work Log 可以引用 UserTask、Reminder、Waiting-For 或 Inbox Item。这些 Target 位于独立
Service 后，在多种情况下还位于不同 SQLite 数据库。标题匹配、人员匹配或 LLM 推断会使
关联不确定，并可能跨越 Workspace 边界。

## 决策

1. 只有调用方提供显式 canonical Target ID 时才存储 Work Log Context Association；
2. 支持 `ut_`、`rem_`、`wf_` 和 `inbox_` 前缀；
3. 每个 Reference 记录 `kind`、`target_id` 和可选有界 `relation`；
4. Kind 与 Prefix 必须一致；格式错误、不支持或重复的 Reference 失败关闭；
5. 格式验证是强 Create 合同；
6. 跨 Service 存在性不是强事务合同，不阻塞 Work Log Create；
7. 不宣称跨数据库 Foreign Key 或事务；
8. Dependency 启用且 Target 在同一 Workspace 可见时，Read path 可 best-effort resolve；
9. Dependency disabled 返回 `not_checked`；Target missing 或 Workspace 不可见返回
   `unresolved`，且不泄露 Target detail；
10. Target 后续消失时，Reference 继续保存并可见，不得静默删除；
11. LLM 输出、标题相似度、姓名、Tag 或自由文本相似度不得创建 Context Reference；
12. 按 Context Reference 查询时，使用精确 canonical Target ID 和完整 Work Log
    Workspace Scope。

## 后果

- Association 可复现、可审计；
- 可选 Service 禁用时仍可创建 Work Log；
- 存储的 Reference 可以比 Target 存活更久，需要显式展示 unresolved；
- 有意不承诺跨数据库强 Referential Integrity。

## 拒绝的替代方案

### LLM 或模糊自动链接

拒绝，因为无法保证确定性 Intent、Workspace 安全或稳定 Replay。

### 强制同步 Target lookup

拒绝，因为可选 Service disabled 时会阻塞合法 Work Log Create，且仍无法提供跨数据库
原子保证。

### 跨数据库 Foreign Key

拒绝，因为 SQLite 数据库是独立权威边界，项目不宣称跨数据库事务。

## 产品实施边界

本 ADR 不新增字段、Model、Lookup、Foreign Key、Schema 或 LLM 行为，只固定未来架构决策。
