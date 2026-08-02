# SP-021：会话式工作交互与确认闭环实施任务规范

## 1. 授权状态

```text
Task:
SP-021 — Conversational Work Interaction & Confirmation Session

Target Release:
v0.36.0 Alpha / Conversational Work Assistant

Planning Base:
5f91d9da224daa9fbb2e68f7a3ba685411e93904

Planning Status:
PLANNING_BASELINE_DEFINED / DRAFT_PR_OPEN /
PENDING_INDEPENDENT_REVIEW

Implementation:
NOT APPROVED / NOT STARTED
```

本文件是未来实施边界，不是实施授权。Planning PR 必须先独立审查、合并并完成 post-merge Quality Gate；Owner 还必须冻结新的 Implementation Base SHA 并明确签发 `SP-021 IMPLEMENTATION APPROVED`。

## 2. 唯一目标

建立一个渠道无关 shared application contract，使 API 与 CEO Assistant 可以安全完成：

```text
canonical query -> Interaction View -> deterministic reference
-> zero-business-write Action Preview -> confirm/cancel/modify
-> canonical service -> database-backed result -> Review/Agenda refresh
```

不得实现第二套业务对象、直接写 SQLite、用 Provider 决定 database ID/成功状态，或提前实现企业微信。

## 3. 推荐实施切分

### SP-021A：Interaction persistence、View 与 Reference

允许：

- 专用 `interaction.db` additive schema initialization/migration；
- View/ViewItem repository、TTL、revision CAS、current replacement 和 cleanup；
- Daily Review/Agenda hydration 与 deterministic ordinal/deictic resolver；
- workspace/session/channel boundary 与 restart tests。

门禁：ACC-021-01～05、12、15 的 A 范围；旧数据库重复初始化；无 canonical 写入；schema/backup/restore contract 通过。

### SP-021B：Preview、Confirmation 与 canonical adapters

允许：

- Preview repository/state machine、confirmation token hash、request/confirm idempotency；
- UserTask、ReminderManagement、WaitingFor、Inbox、WorkLog adapters；
- Confirm/Cancel/Modify、race、stale revision、crash reconciliation；
- structured audit 与 execution/result refresh。

门禁：ACC-021-06～15、20～21 的 service/repository 范围；每个 adapter 保留 revision/claim/Saga；重复 Confirm 恰好一次。

### SP-021C：Proposal 与共享入口

允许：

- strict Proposal schema/validator、deterministic time parser adapter；
- `InteractionSessionService` 接入 API 与 CEO Assistant；
- channel-specific renderer；
- Mock/provider failure zero-side-effect tests。

门禁：ACC-021-16～19；API/CEO 使用同一 service；route/handler 无 direct repository；不接企业微信。

### SP-021D：正式 ACC-021 与证据封存

允许：

- 完整 21 项 end-to-end、restart、concurrency、failure injection、workspace 与 audit 证据；
- 仅修复已批准范围内被验收发现的缺陷。

门禁：ACC-021 21/21 PASSED、独立 evidence review、Quality Gate；未授权不得转 Ready/merge/封存。

依赖顺序：A → B → C → D。它们共享一个 Interaction Session 模型与 application contract，不得各自实现 session。

## 4. Phase 0 强制设计冻结

实施第一处产品变更前必须冻结：

1. 表/索引/unique/CAS/schema-version 设计与旧 data root upgrade；
2. View 30 分钟、Preview 10 分钟建议 TTL 或 Owner 批准替代值；
3. confirmation token 生成、hash、展示与 rotation；
4. action allowlist 和每项 canonical method/revision/idempotency/result reconciliation；
5. `FailureInfo` code/category/HTTP/application status 映射；
6. confirmed crash recovery 判定表、terminal retention 与 cleanup；
7. interaction DB 纳入 quiescent backup/restore；
8. shared response model 与 channel renderer 边界。

任一 action 无法证明安全重放/结果查询时，必须从本轮 allowlist 移除并报告 scope decision，不能用 best effort 执行。

## 5. Canonical execution 约束

| Preview 动作族 | 唯一委托目标 | 不可丢失的门禁 |
|---|---|---|
| task | `UserTaskService` | workspace、expected revision、terminal status、idempotency |
| reminder | `ReminderManagementService` | revision、scheduler bridge、Saga/result facts |
| waiting_for | `WaitingForService` | revision CAS、append-only event |
| inbox | `InboxService` | durable claim、target creation Saga、race recovery |
| work_log | `WorkLogService` | canonical create/get/list；不新增 mutation |
| refresh | `DailyReviewService` / `DailyAgendaService` | read-only、source failure semantics |

Interaction layer 不能调用领域 repository 或 `DatabaseManager` 执行业务写入。它只可操作自己的 persistence repository，再调用 services。

## 6. 共用合同（Shared contract）

application 层至少提供：create View、submit message/proposal、resolve、create/read Preview、confirm、cancel、modify、refresh。核心 request/result 使用结构化 models；API/CEO renderer 不能改变 state、FailureInfo 或 execution outcome。

未来 SP-022 只注入 `channel`、session/reference context 并格式化输出；WeCom signature/decryption/msgid/Outbox 不得进入本任务。

## 7. 安全与失败门禁

- 所有 read/write 使用 canonical workspace filter；未知 ID 不允许跨 workspace probing。
- Provider proposal 不接受 source ID、workspace、revision、confirmation 或 service method。
- Preview 前 canonical 业务数据库零变化。
- pending 是唯一可变/可确认态；Modify 创建新 Preview 并 supersede 旧对象。
- stale/expired/cancelled/superseded/ambiguous 均 fail closed。
- `result_refresh_failed` 保留 consumed execution fact，不伪装回滚。
- audit 保存结构化最小事实，不保存 secret、token、完整 prompt/对话。

## 8. 测试与质量门禁

每个子 PR 至少运行：

```powershell
python -m ruff check <changed-python-files>
python -m pytest tests/governance -q
python -m pytest <targeted-interaction-and-domain-tests> -q
python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no
python -m pytest tests -q --tb=no
git diff --check
```

不得 skip/xfail/删除既有测试或放宽断言。real Provider 不属于普通门禁；正式 ACC 默认 Mock Provider 且真实 Provider calls 为 0。

## 9. 停止条件（Stop conditions）

立即停止并请求新决策：

- Implementation Base 与授权 SHA 不一致；
- Planning PR 尚未合并或 Owner 未授权；
- 需要修改 canonical domain semantics、破坏性 migration 或跨 SP scope；
- 无法保持 workspace/revision/claim/Saga/idempotency；
- crash gap 无法对账或 action 可能重复写入；
- 需要接入企业微信、公开 API、真实凭据、OAuth/JWT/RBAC、多实例/HA；
- ACC-021 需要降低断言才能通过。

## 10. 非目标

Recurring Reminder、外部通知/报价、Knowledge Main Path、Web UI、通用 Agent Runtime、自动 Tool Calling/MCP、自主规划、OAuth/JWT/RBAC、强多租户、个人微信、全聊天历史、语音/图片/文件、多实例/HA、生产 SLA、企业微信实现与 Docker 部署均不在 SP-021。

## 11. 完成状态机

```text
PLANNING_BASELINE_DEFINED
-> PLANNING_APPROVED_AND_MERGED
-> IMPLEMENTATION_BASE_FROZEN
-> IMPLEMENTATION_APPROVED
-> A/B/C IMPLEMENTED_AND_REVIEWED
-> ACC-021 21/21 PASSED
-> FEATURE_PR_APPROVED_AND_MERGED
-> MAIN_QUALITY_GATE_PASSED
-> RECONCILED / ARCHIVED
```

当前只允许停在第一个状态，并等待独立审查。

## 12. 规划依据

- `docs/rfc/030-conversational-work-interaction-confirmation-session.md`
- `docs/adr/ADR-065-persistent-interaction-view-action-preview.md`
- `docs/adr/ADR-066-deterministic-reference-confirmation-state-machine.md`
- `docs/acceptance/SP-021-conversational-work-interaction.md`
