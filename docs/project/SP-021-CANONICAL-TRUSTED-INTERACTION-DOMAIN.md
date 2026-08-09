# SP-021 Canonical Trusted Interaction Domain 实施记录

- 状态：IMPLEMENTATION_AUTHORIZED / OPEN / DRAFT / IMPLEMENTATION_IN_PROGRESS / PENDING_INDEPENDENT_REVIEW / NOT_READY / NOT_MERGE_AUTHORIZED
- Base：`072276207ec0cc0d69372ef38e833c3e1b72ae90`
- Current Product SP：SP-021
- Current Governance Task：None
- 架构权威：RFC-031、ADR-067～068、RFC-032、ADR-069～072

## 目标与授权边界

本 SP 把 ARCH-001 的可信交互合同实现为 AI-Lab 内部可持久化、可查询、可审计、可恢复的 canonical domain。它不接入 Hermes、企业微信、MCP、Browser、Computer Use 或真实外部系统，不增加 Shell-specific HTTP API，也不扩张通用 Agent、Tool、Workflow 或 Coordination Runtime。

INT-001、PILOT-001 与 REL-036 均为 `NOT_STARTED / NOT_APPROVED`。QUALITY-003 与 QUALITY-004 保持 Candidate、未启动、未授权。旧 PR #62 保持 `CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / IMPLEMENTATION_NEVER_AUTHORIZED`。

## 当前实现审计结论

| 能力 | 处理 | 复用方式 |
| --- | --- | --- |
| Composition Root | CORE | `create_system()` 显式装配 repository、Clock 和禁用型 ports |
| DatabaseManager / ConnectionLease / transaction | CORE | Manager 独占 connection 生命周期，关键 mutation 单事务提交 |
| FailureInfo | CORE | 所有应用边界失败继续使用统一 `FailureInfo` / `FailureException` |
| WorkspaceKey | ADAPT | SP-021 禁止空值、默认回退和 actor 不匹配，严格 fail closed |
| revision / CAS | CORE | aggregate 更新必须匹配 expected revision |
| idempotency | CORE | `Workspace + command + key` 持久化；同 key 异 payload 冲突 |
| Inbox resolution Saga | RETAIN | 参考其持久化 claim 与恢复思路，不耦合 Interaction |
| UserTask / Reminder / Inbox / Waiting-For / Work Log | RETAIN | 维持现有行为，本 SP 不迁移既有写入口 |
| Agenda / Daily Review / Action Hint | RETAIN | 维持现有 read model 与行为 |
| Agent / Tool / Workflow / Coordination Runtime | FREEZE | 不扩张、不作为 Trusted Interaction 核心依赖 |
| API chat / CEO Assistant / CLI | ADAPT LATER | 将来经 INT-001 或独立迁移任务接入；本 SP 不增加入口 |

## Canonical aggregate 与事实

`Interaction` 是聚合根，持有 canonical `interaction_id`、Workspace、actor、request/trace correlation、operation、risk/policy、状态、revision 和当前事实引用。以下事实均由 AI-Lab 生成 canonical ID 并持久化：

- `Preview`：零外部副作用，绑定 Workspace、actor、operation、policy、revision 和 expiry；
- `Confirmation`：绑定 exact Preview / revision / actor / Workspace / expiry；
- `Approval`：与 Confirmation 分离，记录 approver role 与独立证据；
- `Execution`：记录 attempt、executor type、idempotency、external reference 与不确定性；
- `VerifiedResult`：记录验证方法、证据摘要、canonical object/revision 与 commit evidence；
- `Recovery`：记录 uncertain/failure 后的恢复状态与证据；
- `AuditEvidence`：重建请求、Preview、授权、执行、验证、恢复和状态转换链。

Channel、Shell、Adapter 和 Transport 标识只能进入 correlation / audit，不能替代 canonical identity。

## 状态机

实现的 ARCH-001 状态为：`REQUESTED`、`PREVIEWED`、`AWAITING_CONFIRMATION`、`AUTHORIZED`、`EXECUTING`、`VERIFYING`、`SUCCEEDED`、`FAILED`、`CANCELLED`、`EXPIRED`、`RECOVERY_REQUIRED`。并分别实现 `ResolutionPhase`、`ExecutionStatus`、`VerificationStatus` 与 `RecoveryStatus`。

关键约束：

- Preview 创建会记录 `PREVIEWED` 证据，再进入 `AWAITING_CONFIRMATION` 或无确认要求的 `AUTHORIZED`；
- Modify 通过创建下一 Preview revision 实现，旧 Preview 原子标记为 `SUPERSEDED`；
- Confirmation 只接受当前 active Preview 的 exact revision；需要 Approval 时 Confirmation 不直接授权执行；
- `AUTHORIZED → EXECUTING` 先持久化 Execution intent，再调用 port；
- accepted / acknowledged / HTTP-like success 只能进入 `VERIFYING`，不能进入 `SUCCEEDED`；
- uncertain outcome 进入 `RECOVERY_REQUIRED` 并同时持久化 Recovery；
- 只有 VerifiedResult 与必要 canonical commit evidence 同时存在，才进入 `SUCCEEDED`；
- 已可能产生外部副作用时，Cancel fail closed，禁止伪造 `CANCELLED`。

## 持久化与 Schema

新增独立 `interactions.db`，按仓库既有初始化约定执行可重复的 additive `CREATE TABLE IF NOT EXISTS`：

| 表 | 职责 |
| --- | --- |
| `interaction_records` | 当前 aggregate snapshot、Workspace、revision 与 lifecycle state |
| `interaction_facts` | Preview、Confirmation、Approval、Execution、VerifiedResult、Recovery |
| `interaction_idempotency` | Workspace-scoped command deduplication 与 payload conflict |
| `interaction_audit` | 有序 canonical audit evidence |

没有修改既有表、ORM、依赖或数据库 ownership。Confirmation+transition、Execution registration+transition、VerifiedResult+terminal transition、Recovery+audit 均在单一事务中提交；任何写入失败整体 rollback。

## Application Service 与 ports

`InteractionService` 提供 transport-neutral 的 create、preview/modify、confirm、approve、cancel、expire、execute、verify/recover、status、view 与 audit 能力。所有 mutation 要求显式 Workspace、actor、expected revision 和 idempotency key。

`ExecutionPort` 与 `VerificationPort` 是最小 Protocol，不 import Hermes、MCP、WeCom、Browser 或 provider SDK。Composition Root 只注入 `DisabledExecutionPort` 与 `DisabledVerificationPort`，因此 production 默认不会产生外部副作用。测试使用确定性的 `ReferenceExecutionPort` 与 `ReferenceVerificationPort`。

## FailureInfo 与安全

身份/Workspace 缺失、跨 Workspace、stale/superseded/expired Preview、Confirmation/Approval conflict、revision conflict、idempotency conflict、execution unavailable/uncertain、verification failure、canonical commit failure 与 recovery required 均投影为现有 `FailureInfo`。敏感 details 继续经现有 redaction；Shell 文本、日志和原始外部响应都不是 canonical audit。

## Restart、ordering 与 recovery

aggregate、facts、idempotency 与 audit 全部落 SQLite。进程重启后 Status 能恢复当前 revision；expired Preview 仍按注入 Clock 判定；同 key 重试不会重复调用 execution port；late command 受 CAS/state precondition 拒绝；uncertain execution 只能进入 verify/recover，不允许 blind retry。

## ACC-021 映射

ACC-021 A～R 的自动证据位于：

- `tests/core/interaction/test_interaction_service.py`：A～G、identity/workspace、expiry、Approval；
- `tests/integration/test_trusted_interaction_persistence.py`：H～N、restart 与 Composition Root；
- `tests/acceptance/test_acc_021_canonical_trusted_interaction.py`：A～R 汇总、uncertain、ordering、FailureInfo、事务回滚；
- 既有 full suite：证明 UserTask、Reminder、Inbox、Waiting-For、Work Log、Agenda、Daily Review 与 Action Hint 无回归。

这些结果只构成 Draft PR 的自动化验收证据，状态仍为 `PENDING_INDEPENDENT_REVIEW`，不得写成 FINAL、Ready 或 Merge Authorized。

## 已知限制

- 没有真实 Execution / Verification Adapter；外部系统验证方式由 INT-001 或后续业务 Adapter 定义；
- 没有 Channel Identity、OAuth、企业微信绑定或多租户 Schema；调用方必须提供已解析的 WorkspaceKey 与 actor；
- policy reference 与 Approval role 已成为 canonical facts，但正式 Policy engine / RBAC 不属于本 SP；
- 现有业务域尚未迁移到 Trusted Interaction Boundary；
- 没有 HTTP、streaming、Shell UI、webhook、poll worker 或自动 recovery worker；Status/View 为 Python application boundary。

## 非目标与授权声明

本 PR 不实现 Hermes、MCP 产品集成、企业微信、真实 Provider、Browser/Computer Use、通用 Runtime 扩张、版本、Tag 或 Release。SP-021 未完成独立审查，未获 Ready 或 Merge 授权；实现者不得自证完成或启动 INT-001、PILOT-001、REL-036、QUALITY-003、QUALITY-004。
