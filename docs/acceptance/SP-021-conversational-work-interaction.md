# ACC-021：会话式工作交互与确认闭环验收规划

## 1. 状态与边界

```text
ACC-021:
PLANNING_BASELINE / NOT_EXECUTED

SP-021:
IMPLEMENTATION_NOT_APPROVED / NOT_STARTED
```

本文件定义未来正式验收证据，不是当前通过记录。正式执行必须冻结 Implementation Head、driver hash、data root、timezone、Provider mode、测试时间和唯一 Run ID；不得用文档断言代替数据库、API、CLI 与 audit 事实。

## 2. 通用夹具

- 隔离 SQLite data root；workspace A/B 各有完整 `WorkspaceKey`。
- fake clock 可推进 View/Preview TTL，固定 IANA timezone 并覆盖 DST 无关的 UTC expiry。
- canonical seed helpers 创建 UserTask、Reminder、Waiting-For、Inbox 与 Work Log，并返回 ID/revision。
- deterministic Mock Provider 可返回合法/非法 Proposal；Provider failure injector 不发真实请求。
- crash harness 可在 Preview claim、canonical commit、result persist、refresh 前后终止并重建 `SystemContainer`。
- side-effect snapshot 记录各领域表、scheduler job、Inbox claim/event 与 interaction tables；Preview-only 写入不算 canonical 业务写入。
- 每个 case 断言 `FailureInfo` code、trace、audit event、workspace 和 canonical result。

## 3. ACC-021 可执行矩阵

| ID | 目标组件与前置数据 | 操作步骤 | 预期结果 | 数据库副作用 | FailureInfo / 注入点 | 测试层级与建议模块 | 阶段 |
|---|---|---|---|---|---|---|---|
| ACC-021-01 | `InteractionSessionService.create_view`；A 有五源今日数据 | 用 A 调用“查看今日工作” | 返回 active View；items 按 Review 稳定顺序、index 从 1 连续；source status 可见 | 新增 View/items/audit；领域表 0 变化 | 注入任一 source failure，保留 partial/source failure，不伪装完整 | service + API integration；`tests/applications/interaction/test_views.py`、`tests/api/test_interaction.py` | A |
| ACC-021-02 | View hydration；已知五个 canonical ID/revision | 对照 items 与各 service `get` | 每个 index 精确映射 type/ID/revision/status；编号不等于 ID | 0 canonical 写入 | hydrate 后对象被删/跨 workspace，item 不可写并记录 source failure | repository/service；`test_view_hydration.py` | A |
| ACC-021-03 | Resolver；active View index 1 | 提交“完成第一条任务” Proposal | 唯一解析 index 1，fresh read 后生成相同 target Preview | 只写 Preview/audit | index 越界→`reference_not_resolved` | unit + service；`test_reference_resolution.py` | A/B |
| ACC-021-04 | scope 已有 View V1 | 创建 V2，再用 V1“第一条” | V1 superseded；旧引用不执行；V2 成为唯一 current | V1 state + V2/items；领域 0 | `interaction_view_superseded` | repository + service；`test_view_lifecycle.py` | A |
| ACC-021-05 | 同 scope 人为制造歧义/无唯一 deictic anchor | 提交“刚才那个” | 不创建可执行 Preview，不调用 service | canonical 0；只允许 failure audit | `reference_ambiguous`；注入双候选/current invariant violation | unit + failure injection；`test_reference_resolution.py` | A |
| ACC-021-06 | 唯一 target、allowlisted action | 提交合法写 Proposal | 返回 pending Preview，包含 target/revision/action/normalized args/effect/expiry/token | 仅 Preview/audit | invalid args→`invalid_proposal` | service；`test_preview_service.py` | B |
| ACC-021-07 | canonical side-effect snapshot | 创建所有 allowlisted Preview，未 confirm | 前后 Task/Reminder/Waiting/Inbox/WorkLog/Scheduler 完全一致 | canonical 0 | 在 adapter spy 断言未调用 | service + repository；`test_preview_zero_side_effect.py` | B |
| ACC-021-08 | pending Preview 与正确 token | Confirm | 仅调用映射的 canonical method；返回数据库事实；Preview consumed；Review/Agenda 刷新 | 恰好一个预期业务变化 + result/audit | service 在 commit 前 failure→`canonical_execution_failed` | service + API/CEO integration；`test_confirmation.py` | B/C |
| ACC-021-09 | pending Preview | Cancel 后 Confirm | Preview cancelled；目标不变；后续 Confirm fail closed | Preview/audit；canonical 0 | `preview_cancelled` | service + API；`test_confirmation.py` | B |
| ACC-021-10 | pending Preview P1 | 修改时间/备注/目标 | P1 superseded；重新验证并创建 P2；token/idempotency 均不同 | interaction state only | 新参数非法→`invalid_proposal` 且 P1 的终态按事务合同可证明 | service；`test_preview_modify.py` | B |
| ACC-021-11 | P 捕获 revision r；外部合法写到 r+1 | Confirm P | fresh read 发现冲突；P failed；不执行目标动作 | 外部 seed 写之外，Confirm canonical 0 | `stale_revision`，details 含 expected/actual | service + race；`test_stale_revision.py` | B |
| ACC-021-12 | pending Preview + fake clock | 推进到 `expires_at` 后 Confirm | Preview expired，不执行；cleanup 前后语义一致 | expiry/audit；canonical 0 | `preview_expired` | repository + fake clock；`test_expiration.py` | A/B |
| ACC-021-13 | 可执行 Preview | 并发/顺序 Confirm 两次 | 一个 winner；第二次返回同一 saved result；业务变化恰好一次 | canonical 1 次 | CAS barrier/commit gap；terminal 可返回 `preview_already_consumed` 或 idempotent success contract | concurrency + recovery；`test_confirmation_race.py` | B |
| ACC-021-14 | pending、confirmed-at-crash、consumed 三类 Preview | 关闭并重建 SystemContainer | pending 不自动执行；confirmed 对账；consumed 可重读且不重放 | 无未授权写入 | crash 分别注入 claim 后、canonical commit 后、result persist 前 | restart/recovery；`test_interaction_recovery.py` | B/D |
| ACC-021-15 | A/B 均有 session、View、Preview，ID 可被对方获知 | B 读取/解析/confirm A 对象 | 全部 fail closed，无存在性泄露式执行 | canonical 0 | `workspace_mismatch` 或统一 not-found policy | workspace isolation + API headers；`test_workspace_isolation.py` | A/B/C |
| ACC-021-16 | 同 seed/shared SystemContainer | API 与 CEO Assistant 分别 create/preview/confirm | 两入口调用同 `InteractionSessionService`，状态/FailureInfo/结果等价，仅 rendering 不同 | 由共享服务产生同一类事实 | spy 禁止 route/handler 直调 repository | API + CEO integration；`tests/api/test_interaction.py`、`tests/applications/test_ceo_interaction.py` | C |
| ACC-021-17 | active View 只含 ID A；Mock Proposal 注入 ID B | submit proposal | strict schema/validator 拒绝 Provider-supplied ID；不查写 B | canonical 0；failure audit | `invalid_proposal` | unit + provider contract；`test_proposal_validation.py` | C |
| ACC-021-18 | active View；Mock 输出未知 action | submit proposal | action allowlist 拒绝，不创建可执行 Preview | canonical 0 | `action_not_allowed` 或 `invalid_proposal`（冻结其一） | unit；`test_proposal_validation.py` | C |
| ACC-021-19 | Provider timeout/unavailable/malformed JSON | 提交自然语言写请求 | FailureInfo 可见，不 fallback/猜测，不调用 canonical service | canonical 0 | `provider_unavailable`/`invalid_proposal`；provider injector | CEO/API failure injection；`test_provider_fail_closed.py` | C/D |
| ACC-021-20 | action 会改变今日 Review/Agenda | Confirm 后读取 response refresh 与独立 query | execution result revision/status 与独立 DB query 一致；新 View supersede 旧 View | 一个 canonical 写 + refresh View | refresh injector→`result_refresh_failed`，Preview 仍 consumed | end-to-end + service failure；`test_result_refresh.py` | B/D |
| ACC-021-21 | 成功、stale、workspace、provider、refresh cases | 查询 response 与 audit | trace 串联 proposal/View/Preview/confirm/execution/refresh；audit 含结构化最小字段且无 secret/token/full prompt | 仅所测预期变化 | audit persist failure 与 FailureInfo serialization injector | repository + integration + security；`test_interaction_audit.py` | B/C/D |

## 4. Canonical action 覆盖

正式验收必须对以下 adapter 至少各取一个成功、一个 stale/invalid、一个重复请求 case：

- UserTask complete/cancel/update/reopen；
- Reminder cancel/reschedule（含 scheduler bridge/Saga）；
- Waiting-For follow_up/snooze/resolve/cancel/reopen；
- Inbox resolve/dismiss（含 durable claim 和恢复）；
- Work Log create（不虚构 edit/complete/delete）。

未能证明 canonical idempotency/result reconciliation 的 action 不得留在 allowlist，也不得通过降低 ACC 覆盖规避。

## 5. 证据要求

正式 Evidence Package 至少包含：

```text
Frozen Implementation Head
Driver SHA-256
Run ID / start-end timestamps / timezone / fake-clock policy
Python / pytest / ruff versions
21 项逐项 PASS/FAIL 与测试节点
canonical table before/after digest
interaction View/Preview/audit facts（secret-safe）
workspace A/B isolation evidence
restart/crash injection checkpoints
Provider Calls（Mock 应为 0 real calls）
non-real Quality Gate 与 full pytest 结果
unexpected files / tracked diff
```

任何 case 未执行、依赖真实 Provider、存在未解释写入、复用旧 evidence 或需要手工猜测数据库结果时，ACC-021 不得标为 PASSED / FINAL。

## 6. 验收门禁

建议阶段门禁：

- Phase A：ACC-021-01～05、12（View/Reference/TTL/workspace repository 基础）。
- Phase B：ACC-021-06～15、20～21 的 service/repository 部分。
- Phase C：ACC-021-16～19 与 API/CEO shared contract。
- Phase D：全部 21 项独立正式执行、故障注入、restart 与 evidence review。

当前仅完成 traceability planning：21 / 21 已映射，0 / 21 已执行。
