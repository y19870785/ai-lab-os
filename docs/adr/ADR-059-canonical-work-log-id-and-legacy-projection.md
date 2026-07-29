# ADR-059：规范 Work Log ID 与只读 Legacy Projection

Status: Accepted

> 这是 SP-018 规划基线的 Accepted 架构决策，不批准或启动产品实施。

## 背景

CEO Assistant Work Log 当前使用通用随机 Memory ID；Inbox conversion 使用历史确定性
`inbox_wl_...` ID。既有 Row 可能缺少完整 Workspace、timezone 或类型字段。删除、重写
或导入它们会带来重复、数据丢失和 Identity 漂移风险。

## 决策

1. 新 Work Log 使用 canonical `wl_<32 lowercase hex>` ID；
2. 新 Row 的 `WorkLogRecord.id` 与 `episodic_memories.id` 使用同一值；
3. 直接 Create 使用加密安全随机 hex，并以 insert-only collision retry；
4. Inbox Create 从 Inbox Item ID 确定性推导 32 hex payload；碰撞时只有存储 Source
   与该 Inbox 相同才能恢复，否则失败；
5. Legacy Row 投影为 `wl_legacy_<full sha256 of legacy memory id>`；
6. Projection 跨进程与重启保持确定，保留 `legacy_memory_id`，且不写新 Row；
7. 公开 API/CLI lookup 接受 canonical `wl_...` 与 `wl_legacy_...`；普通随机 Memory ID
   保持内部使用，拒绝作为公开 Alias；
8. 历史 `inbox_wl_<valid legacy format>` 是唯一受限兼容 Alias。Lookup 必须找到同 ID
   Row，证明 `content.type == "work_log"`、Inbox 来源证据一致，并执行完整 WorkspaceKey；
9. 合法 Inbox Alias 返回同一对象的 canonical
   `wl_legacy_<full sha256 of inbox_wl_ row id>` Projection，不创建第二 Row；
10. 既有 `InboxItem.resolved_target_id`、`InboxResolutionClaim.target_id`、Event payload、
    retry 与 crash-recovery 状态继续保留 `inbox_wl_...`，不得重写；
11. 缺少完整 Workspace 的 Legacy Row 只归属 canonical `default/default/default`；
12. Legacy 时间优先使用显式 occurred_at/date，其次使用持久化 Memory timestamp，
    不得以当前时间替代；
13. Projection failure 以 `work_log.legacy_projection_failed` 可见，不静默丢弃不兼容数据；
14. `inbox_wl_...` 不是 Context Reference；新 Context Reference 只能使用 Inbox Item
    Identity `inbox_...`。

## 后果

- 所有公开消费方获得带类型的稳定 ID；
- 既有 Row 保持不变且可追溯；
- Legacy lookup 需要确定性 digest lookup 和 Repository 内受限 Inbox Alias 路径；
- Alias 与 canonical lookup 返回一个逻辑对象，且都为零写入；
- Raw status 或不完整字段必须用显式 legacy Projection metadata 表达，不能伪装满足新合同。

## 拒绝的替代方案

### 暴露既有随机 Memory ID

拒绝，因为它不标识产品类型，会让 API、CLI、Agenda 与 Brief 保持不同 Identity 合同。
唯一 `inbox_wl_...` 例外来自已经公开的历史 Inbox 合同，使用前必须验证。

### 原地重写 ID

拒绝，因为 Inbox resolution claim 与外部引用可能依赖原 Row ID，操作具有破坏性且难回滚。

### 导入重复 canonical Row

拒绝，因为 Retry 可能制造重复，推断的 Workspace 或时间也可能错误。

## 产品实施边界

本 ADR 只定义 Identity 与兼容性。规划基线不执行 Migration、write-back、Alias Table、
Schema 变更或产品实施。
