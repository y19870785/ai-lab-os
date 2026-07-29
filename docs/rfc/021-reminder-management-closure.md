# RFC-021：提醒管理闭环

**状态：** Adopted
**范围：** Reminder 管理、可操作 Inbox 语义、确定性响应与本地 CLI 输出
**合并状态：** 由 SP-011 实施并通过 PR #23 合并

## 采纳记录

- 由 SP-011 实施。
- 通过 PR #23 合并。
- Approved Head：`beb99115dd273a9fe55e86d21e65f714e7f7f52f`。
- Merge Commit：`5c4b442b2b5c7f934ac381020ba8b310976d5d3a`。
- 采纳日期：`2026-07-17`。

## 背景

SP-009 创建了持久化自然语言 Reminder 链路，SP-010 使 Reminder 可被发现。用户仍需要一个共享边界来解析、查看、取消和重新安排 Reminder。既有跨数据库 Reminder/Scheduler Saga 继续作为权威来源；本 RFC 不引入第二套事务模型。

## 用户问题

- 未来已取消 Reminder 会出现在宽泛的 `upcoming` 结果中，尽管它已经不可操作。
- API、CLI 与 CEO Assistant 可能演化出不同的管理规则。
- 即使没有使用 Provider，确定性 Reminder 操作也可能收到 Mock/LLM 模式文本。
- Windows CLI 捕获输出依赖外部编码覆盖。

## 管理边界

组合根只创建一个 `ReminderManagementService`。该服务拥有工作空间验证、目标解析、终态规则、稳定失败、幂等 metadata，以及向 `ReminderSchedulerBridge` 的委托。API 路由、CLI 命令与 CEO Assistant 不直接写入 Reminder 或 Scheduler 持久化。

## 解析与歧义

只有关联 UserTask 属于请求工作空间时，系统才接受精确 Reminder ID。标题匹配仅限当前工作空间；唯一精确匹配或子串匹配可以解析，多个匹配以 `reminder.ambiguous` 和有界候选 fail closed，不存在可见匹配时返回 `reminder.not_found`。

## 取消语义

处于 scheduled 或 retrying 的 Reminder 通过既有 Bridge Saga 取消。Reminder 与 Scheduler Job 都进入 cancelled；重复取消保持幂等，旧到期时间不会创建 occurrence。triggered 与 failed Reminder 对取消操作属于终态。部分失败返回 `reminder.cancellation_failed`，持久化的 pending/失败状态仍可查询。

## 重新安排语义

scheduled、retrying 与 failed Reminder 可以重新安排；triggered 与 cancelled Reminder 以 `reminder.terminal_state` 拒绝操作。Bridge 尽可能更新既有 one-shot Scheduler Job，保留 UserTask 关系，并且只在协调成功后把 Reminder 恢复为 scheduled。先前失败码保留在 `management_reschedule` 审计 metadata 中，当前 `last_failure` 被清除。

## Saga 与补偿

Reminder 与 Scheduler 数据库继续作为独立持久化边界。管理操作复用 Bridge 的 pending 状态与对账行为，不声称跨数据库原子性，也不得在 Bridge 失败后返回成功。查询聚合把携带 `last_failure` 的 pending 管理状态显示为 failed，直到恢复完成。

## 幂等性

取消操作天然幂等。重新安排接受显式 idempotency key，只将 SHA-256 摘要与目标 UTC 时刻一同存储，绝不存储原始键。相同键与目标复用持久化结果；相同键配合不同目标以 `reminder.idempotency_conflict` 失败。重新安排复用既有 Scheduler Job ID，不创建重复的 active Job。

## 待处理 Inbox 语义

`view=pending` 表示 `status in (scheduled, retrying)` 且 `scheduled_for >= now`。`status=cancelled&time_scope=upcoming` 等显式组合继续有效。为保持兼容，无参数 API 与 CLI 列表继续返回全部 Reminder。确定性短语“查看我的提醒”选择 pending 项，并单独报告终态数量。

## 确定性响应边界

Reminder 创建、Inbox、详情、取消和重新安排均为确定性应用响应。它们设置内部响应标记，避免追加 Provider 模式提示。普通 LLM chat 继续保留既有显式 Mock 模式提示。API 或展示边界不得删除响应文本。

## CLI UTF-8 边界

仅当 stream 支持 `reconfigure` 时，CLI 才以 replacement 模式把 stdout 与 stderr 重新配置为 UTF-8。JSON 使用 `ensure_ascii=False`，诊断信息写入 stderr。进程不修改 Windows 系统代码页，也不要求持久设置 `PYTHONIOENCODING`。

## 工作空间隔离

所有管理和状态读取都验证关联 UserTask 的服务端工作空间 metadata。跨工作空间 ID 返回 `reminder.not_found`，避免泄露对象是否存在。这是逻辑工作空间隔离，不是用户身份、RBAC 或强多租户安全模型。

## 验收策略

测试覆盖取消且不生成 occurrence、重启安全的重新安排、旧时间抑制、新时间只生成一个 occurrence、终态规则、唯一与歧义解析、故障注入、pending 过滤、确定性响应、真实组合根装配、真实 FastAPI lifespan、SQLite 持久化与子进程 UTF-8 JSON 输出。

## 已知限制

外部通知、系统通知、Recurring Reminder、批量管理、模糊语义搜索、多轮引用、用户身份、RBAC、强多租户、Web UI 与分布式调度不在范围内。跨 SQLite Inbox 读取不是快照事务，深度稀疏分页仍是性能观察点。
