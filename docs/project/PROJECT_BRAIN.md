# AI-Lab Project Brain —— 项目大脑

> 产品版本：v0.35.0
> 最近完成的 Product SP：SP-020
> 当前 Product SP：None
> 当前治理任务：STRAT-001
> 下一候选 Product SP：None
> 下一候选方向：None
> STRAT-001 状态：PLANNING BASELINE / DRAFT PR / PENDING INDEPENDENT REVIEW / NOT_MERGED
> 战略定位：面向个人经营者和企业真实工作流的可信业务操作系统
> Agent Shell：Hermes 为首选但可替换；不得直接访问 AI-Lab 数据库
> PR #62：OPEN / DRAFT / FROZEN_PENDING_STRAT_001 / NOT_READY / NOT_MERGE_AUTHORIZED / IMPLEMENTATION_NOT_APPROVED
> SP-020 状态：APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED
> ACC-020 状态：PASSED / FINAL
> SP-020 已批准实现 Head：`1c9b69ee45b4e1545b67ecd841cc217e23d4f38f`
> ACC-020 验收证据 Head：`7a0944f4ad1deadefe636bf5abc3d30175de0b4d`
> ACC-020 正式运行：`ai-lab-acc020-formal-20260730-175832-eda685f89c274e6cb520c0aaa964b3dc` / Provider Calls `0` / Evidence Review `APPROVED`
> SP-020 设计：RFC-029 Adopted；ADR-063 与 ADR-064 Accepted
> SP-020 规划合并：PR #53 / `fbd10fb5c4cd3913bb70d0c17cdd6df9de196625` / main Quality Gate `30441534383` / SUCCESS
> SP-020 功能合并：PR #57 / `9ea4b72241bd855319231c09fa6b80c112a14305` / main Quality Gate `30687851816` / SUCCESS
> SP-020 对账：SP-020A / PR #58
> REL-035 状态：FINAL_RECONCILED / ARCHIVED
> v0.35.0：Local Daily Operating Loop / PRE_RELEASE_PUBLISHED / REMOTE_VERIFIED / Binary Assets None

STRAT-001 将业务事实、状态、规则、Preview、Confirmation、Approval、Audit、Verified
Result 与 Recovery 固定为 AI-Lab 权威；Hermes Memory、Conversation 和 Tool Response
分别不得充当业务事实、审批事实或最终成功证明。通用 Agent、渠道、Skills、Browser、
Computer Use 和通用 Cron 优先由 Agent Shell 提供；AI-Lab 保留业务 Reminder/Scheduler。
v0.36 的治理顺序固定为 `STRAT-001 → ARCH-001 → SP-021 → INT-001 → PILOT-001 → REL-036`，
但除 STRAT-001 外均未获启动授权。

```text
SP-020:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
ACC_020_PASSED /
INDEPENDENT_EVIDENCE_REVIEW_APPROVED /
RECONCILED /
ARCHIVED

ACC-020:
PASSED / FINAL

Approved Implementation Head:
1c9b69ee45b4e1545b67ecd841cc217e23d4f38f

Acceptance Evidence Head:
7a0944f4ad1deadefe636bf5abc3d30175de0b4d

Formal Run:
ai-lab-acc020-formal-20260730-175832-eda685f89c274e6cb520c0aaa964b3dc

Provider Calls:
0

Evidence Review:
APPROVED

Feature Merge Commit:
9ea4b72241bd855319231c09fa6b80c112a14305

Main Quality Gate:
30687851816 / SUCCESS

Reconciliation PR:
58
```
> SP-016 状态：APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / COMPLETED / ARCHIVED
> ACC-016 状态：PASSED / FINAL
> SP-017 状态：APPROVED / MERGED / ACCEPTED / RECONCILED / ARCHIVED
> ACC-017 状态：PASSED / FINAL
> SP-017 设计：RFC-026 Adopted；ADR-056 与 ADR-057 Accepted
> SP-018 状态：APPROVED / MERGED / ACCEPTED / POST-MERGE VERIFIED / RECONCILED / ARCHIVED
> ACC-018 状态：PASSED / FINAL
> SP-018 设计：RFC-027 Adopted；ADR-058、ADR-059 与 ADR-060 Accepted
> SP-019 状态：APPROVED / MERGED / POST_MERGE_VERIFIED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED
> ACC-019 状态：PASSED / FINAL
> SP-019 设计：RFC-028 Adopted；ADR-061 与 ADR-062 Accepted
> SP-019 规划合并基线：`e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / Quality Gate run `30205853257` / SUCCESS
> SP-019 功能合并：`a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49` / Quality Gate run `30382312419` / SUCCESS
> 发布阶段：v0.35.0 Alpha / PRE_RELEASE_PUBLISHED
> 已验证发布基线：`22f88d1da962fb436c48c19e5343fad8bf62f5f6` / Quality Gate run `29855987444`
> SP-015 Base Commit：`57444274abd4e568a6af72b218d50290de563654`
> SP-015 分支：`chore/sp-015-release-governance-consolidation`
> SP-015 状态：APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED
> SP-015A 状态：APPROVED / MERGED / RECONCILED / ARCHIVED
> SP-015R 状态：APPROVED / MERGED / RECONCILED / ARCHIVED
> Previous Authorized Tag: v0.34.0
> v0.35.0 Tag：ANNOTATED / REMOTE_VERIFIED
> v0.35.0 GitHub Release：PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED / Assets 0

`Verified Release Baseline` 是最终发布提交之前经独立 main Quality Gate 验证的历史基线，不声明等于包含本文件的当前提交。当前 HEAD、Tag 与 GitHub Release 的存在性、目标、URL 和时间通过 Git/GitHub 查询；仓库根目录 [project_state.json](../../project_state.json) 记录稳定的项目与发布授权状态。

当前 GitHub main HEAD、Pull Request 状态和最新 Workflow run 都是应通过 Git/GitHub 实时查询的外部事实；治理文档不维护会随自身提交立刻过时的 `Current main` 镜像。

## 项目使命

AI-Lab 是面向个人经营者和本地工作流的 AI Operating System 基础设施。它以长期运行、可演化、Provider Agnostic 为设计目标，从任务、提醒、工作记录、日程、收件箱和知识基础设施支撑真实经营活动。

AI 可以收集、整理、分析和提醒；最终业务判断与重要审批仍由用户负责。

## 治理事实来源

| 载体 | 职责 |
|---|---|
| `project_state.json` | 唯一机器可读仓库治理状态：版本、已验证历史基线、SP、Quality Gate、技术债与发布授权配置 |
| `pyproject.toml` | 唯一运行时产品版本、依赖与 package discovery 来源 |
| `README.md` | 产品定位、安装、当前稳定能力、限制与文档入口 |
| `PROJECT_BRAIN.md` | 长期架构事实、关键决策和封存产品事实 |
| `ROADMAP.md` | 未来版本范围、里程碑与候选任务，不承担历史流水账 |
| `CHANGELOG.md` / Release Notes | 版本对应的用户可见变化、升级说明与已知限制 |
| RFC / ADR | 重大方案设计 / 已作出的架构决策 |
| SP 任务书 | 单次实现、验证与验收边界 |

文档不得建立第二份机器状态；运行时版本不得在 Python 源码中硬编码。

### DOCS-001 永久治理事实

DOCS-001 已通过独立审查。Approved Head
`d7a6662dddaac87b41562e2348f69e04112b2be4` 由 PR #55 Squash Merge 为
`2d04f1b8574fde43b1d64a53d1ad22573073a4ef`，合并时间为
`2026-07-29T14:43:26Z`；main Quality Gate run `30462290819` 为 SUCCESS。

该任务确立了 176 个 Git 跟踪 Markdown 文件的中文治理基线，以及
`DOCUMENTATION_POLICY.md`、`MARKDOWN_INVENTORY.md`、
`TERMINOLOGY_GLOSSARY.md` 与自动化 Markdown 治理门禁。DOCS-001 已完成
合并后对账并封存。当前 Governance Task 是 None；DOCS-001 没有修改产品代码、
产品版本、Tag 或 Release，也没有授权或启动 SP-020 产品实施。

## 永久架构事实

### 规范组合根

唯一入口是 `core/system/factory.py:create_system()`，容器定义在 `core/system/container.py`。API lifespan、CLI、CEO Assistant、兼容 Bootstrap 与集成测试共用同一 Factory 和领域服务装配。

默认策略：

```text
Knowledge: disabled
Scheduler / Reminder: disabled unless explicitly enabled
Coordination: disabled
Mock Provider: only explicit mock/test profiles
```

### 统一失败与生命周期边界

- `FailureInfo` 是 Agent、Task、Scheduler、API、事件与 System Health 的统一失败契约。
- API 与内部工作入口共享 lifecycle-backed admission boundary；Scheduler 是独立 producer 边界。
- 已接纳工作可以在 draining 后完成；进程级 in-flight counter、drain timeout 与多进程 admission coordination 仍未实现。

### SP-020 规划边界

- SP-020 只定义 Windows Local Daily Profile、正式 Daily Review CLI、纯确定性 Action
  Hint、canonical Review-to-Action 委托、进程重启与 Quiescent Backup/Restore。
- 默认 data root 当前跟随 working directory 推导；未来 Local Daily Profile 必须使用
  稳定绝对路径并显式展示非敏感有效配置。
- Daily Review 与 Action Hint 保持只读、无数据库、无事件、无 LLM、无 snapshot；
  所有写入继续委托现有 canonical domain services。
- 当前 `SystemContainer` 关闭流程会两次调用 Scheduler shutdown。Phase 0 必须正式
  证明幂等、partial-start rollback、连接释放与 restart recovery，不能只依赖代码推断。
- 备份默认只承诺优雅停机后的完整 data directory 复制与隔离恢复，不承诺在线跨库
  一致快照。
- 历史规划基线建立时，Implementation 已获授权，Phase 0 已通过，Phase 1～3 已实现并完成自动化验证；当时 ACC-020 尚未执行。当前最终状态以本页顶部治理摘要为准。

### 数据与 Workspace 边界

- DatabaseManager 是受管 Memory SQLite 连接的 Owner；Store 不关闭 borrowed connection。
- UserTask、Reminder、Daily Agenda 与 Unified Inbox 使用 canonical `WorkspaceKey` 逻辑隔离。
- Workspace 隔离不是用户身份、RBAC 或强多租户授权。
- 跨 SQLite 业务使用显式 Saga、幂等键与 reconciliation，不宣称跨库原子事务。

### SP-014 永久产品事实

- Unified Inbox 与 Capture-to-Action 通过 PR #32 进入 `main`；ACC-014 A～L 全部 PASSED。
- API、CLI 与 CEO Assistant 共享 Composition Root 注入的 `InboxService`。
- 支持显式转化为 UserTask、Reminder、Work Log、Note 或 Dismiss。
- `inbox_resolution_claims` 是跨 API worker、CLI 进程与独立 Service 实例的唯一解析权和崩溃恢复边界；进程内锁只是优化。
- Workspace 隔离、幂等、不同类型竞争、同类型竞争、restart persistence 和两个中断恢复点已通过真实验收。
- SP-014B 通过 PR #33 支持明确 `上午/下午/晚上` 下中文小时 `一` 至 `十二`；不扩展复杂日期、相对/模糊时间、Recurring Reminder 或 LLM 时间解析。
- SP-014 治理对账通过 PR #34 合入 `57444274abd4e568a6af72b218d50290de563654`。

### SP-017 永久产品事实

- 自然语言 Waiting-For 创建必须经过 `Inbox capture -> Inbox ID confirm -> resolve_to_waiting_for`；模糊表达只创建 pending Inbox，不直接创建 Waiting-For。
- 后续 lifecycle mutation 必须使用 canonical `wf_...` ID。
- Inbox-to-Waiting-For 复用 `CLAIMED -> TARGET_CREATED -> COMPLETED`，Waiting-For ID 由 Inbox ID 确定性派生。
- 重复确认、崩溃恢复和跨进程竞争最终只产生一个目标。
- LLM 不参与写入判断、字段补猜或成功证明。
- API 和 CLI 缺省 timezone 统一使用系统 `timezone_name`。
- 显式 `POST /waiting-for` 和 `waiting-for create` 继续支持直接创建。

### SP-018 永久产品事实

- 唯一 `WorkLogService` 已在 Composition Root 中装配；CEO Assistant、API、CLI、Inbox、Daily Agenda 与 Daily Brief 共用该边界。
- `episodic.db / episodic_memories` 继续作为物理存储；不会创建 `work_logs.db`、第二张 Work Log 表或 SP-018 索引。
- Work Log 查询以完整 `tenant_id + workspace_id + namespace` 为 Workspace identity，在 SQL 候选阶段先隔离。
- 新记录使用 `wl_...` canonical ID；旧随机 Memory ID 通过确定性 `wl_legacy_...` 只读投影兼容，不写回。
- 上下文关联只接受显式 `ut_`、`rem_`、`wf_`、`inbox_` ID；不使用 LLM 或相似文本猜测。
- Feature PR #46 已以 Squash Merge 合入 `83ecb557fedd1d898712afc59ad13b3e0a684413`；ACC-018 A～O 在 Approved Head `e941cadc783a6ac8a4bd3c75b55adf77e0a651a3` 完整通过。
- 合并后的 main 通过自动 push Quality Gate `30196719409`、本地全量验证与 post-merge smoke；验收和 smoke 均未调用真实 Provider。
- SP-018A 对账 PR #47 已合并为 `4e0d730a8bfdefa6277c7526a028e7247d7ddc43`，自动 push Quality Gate `30198434517` 成功。
- SP-019 Planning Baseline 已通过独立审查并由 PR #48 Squash Merge 到 main `e7fc5b1dd66ff7828c1697bfd5610f300599eee5`；Approved Planning Head 为 `282dd939ff264b0f23d5070b6f632aa0442531ea`，合并时间为 `2026-07-26T14:19:41Z`，自动 push Quality Gate `30205853257` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。当时 RFC-028、ADR-061、ADR-062 为 Proposed / Planning Baseline，且规划批准与合并本身不构成 SP-019 Implementation 授权；当前验收后状态见本页顶部。
- UserTask Workspace Query Closure 是 SP-019 的已验收 Phase 0；PR #50 已合并并通过 post-merge Quality Gate。

### SP-019 永久产品事实

- Daily Review 是非持久化、确定性、只读 read model；不拥有数据库、表、事件、生命周期或持久化 snapshot。
- 唯一聚合边界是 `DailyReviewService`，直接读取 `WorkLogService`、`UserTaskService`、`WaitingForService`、`ReminderInboxService` 与 `InboxService`。
- API、CEO Assistant 与兼容 `/brief` 委托同一 `DailyReviewService`，不维护第二套聚合事实。
- Review date 只支持 `today` / `yesterday`；日期事实由 `review_date` 控制，当前未闭环状态（包括 pending Inbox）由 `as_of` 决定。
- Feature PR #51 已以 Squash Merge 合入 `a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`，合并时间为 `2026-07-28T17:18:41Z`；main Quality Gate `30382312419` 的 Ruff 与 pytest (non-real) 均为 SUCCESS。
- ACC-019 A～M 在 Approved Implementation Head `1f2975503cd79047137a4a9f47096668fd4341c5` 上全部通过，Acceptance Evidence Head 为 `420da28664914fda8ccbecadf90947380ec43473`；没有真实 Provider 调用。

## 已封存产品能力

| 能力 | 当前事实 |
|---|---|
| Single Composition Root | 已集成并验证；所有正式入口共用 SystemContainer |
| DatabaseManager ownership | 已集成并验证；受管连接、lease、关闭与恢复语义稳定 |
| Canonical UserTask | 已集成并验证；真实领域、`tasks.db`、API 与 CEO Assistant 路径 |
| Reminder Core | 已集成并验证；持久化 Reminder、Scheduler Job、Occurrence 与 Saga |
| Reminder Inbox / Management | 已集成并验证；查询、详情、取消、改期、workspace 与幂等合同 |
| Intent Safety | 已集成并验证；read/write/chat 显式分离，模糊查询优先只读 |
| Daily Agenda | 已集成；可选聚合 UserTask、Reminder、Waiting-For 与 Work Log |
| Daily Review | 已集成、验证并通过人工验收；确定性聚合五个 canonical services |
| Waiting-For | 独立 canonical domain、`followups.db`、API/CLI、确定性交互与 append-only history 已通过人工验收并封存 |
| Unified Inbox | 已集成并通过 ACC-014；Capture-to-Action 与持久化 resolution claim |
| API Security | Bearer Token 与 CORS allowlist 已集成；尚无用户身份和 RBAC |

历史 PR、Head、merge commit、合并时间和各 SP 状态集中保存在 `project_state.json`，不在本文件重复维护完整流水账。

## 当前模块状态

| 模块 | 状态 | 边界 |
|---|---|---|
| Governance | Integrated / SP-015, SP-015A and SP-015R archived | 统一机器状态、版本、文档职责与一致性测试 |
| EventBus / Database / Memory | Integrated / Verified | 本地持久化主链路 |
| Provider | Integrated / Verified | Mock 路径属于普通门禁；真实 Provider 需单独授权 |
| Knowledge | Implemented / Disabled | 真实主链路、reindex、chunk persistence、citation 未完成 |
| Agent / Tool / MCP | Integrated foundation | 完整 Agent 产品闭环、自动 Tool Calling 与完整 MCP 闭环未完成 |
| Workflow / Task Runtime | Integrated / Verified | 运行时和失败语义已验证 |
| Scheduler / Reminder | Integrated / Verified / Disabled by default | 外部通知与 Recurring Reminder 未实现 |
| UserTask / Daily Agenda / Daily Review / Unified Inbox | Integrated / Verified | Agenda 支持可选来源组合；Daily Review 已通过 ACC-019 A～M |
| Waiting-For | Integrated / Verified / Manual acceptance passed | SP-016 与 SP-017 completed / archived |
| Coordination | Implemented / Disabled | 未接入 CEO Assistant 主链路 |
| CEO Assistant / API / CLI | Integrated / Verified / Alpha | local-first，不是 production-ready 产品 |

## 验证基线

最终发布提交前的已验证 main 基线事实来自 GitHub Actions run `29855987444`：

```text
Environment: ubuntu-latest / Python 3.12
Ruff: SUCCESS (changed Python files only)
pytest (non-real): 1163 passed, 6 skipped, 27 warnings
tests/real: explicitly excluded
```

历史本地测试只能作为对应时间和环境的记录，不替代当前 GitHub Quality Gate；真实 Provider 结果也不由普通门禁推导。

## v0.34.0 Alpha / 已授权发布

本 Alpha 版本收口 UserTask、Reminder Core、Reminder Management、Intent Safety、Daily Agenda、Unified Inbox、Capture-to-Action、统一 Composition Root 和治理一致性。

明确不包含：

- 外部通知与 Recurring Reminder；
- Web UI；
- 完整 Knowledge 主链路；
- 用户身份、OAuth/JWT/RBAC 与强多租户；
- 企业级部署或生产可用性承诺。

SP-015R 已合并、通过 main Quality Gate 并封存；Owner 与 ChatGPT 已授权 Tag `v0.34.0` 和 GitHub Pre-release。Tag 是否存在及其目标、Release 发布状态、URL 与时间均以 GitHub Tags and GitHub Releases 为权威来源，仓库不维护这些外部事实的实时布尔镜像。

## v0.35.0 Alpha / GitHub Pre-release 已发布

REL-035 将 SP-016～SP-020 已验收能力定义为 `v0.35.0 Alpha — Local Daily
Operating Loop`，并建立数据兼容、配置升级、Release Notes、验证矩阵和独立授权状态机。
当前源码版本为 `0.35.0`；annotated Tag `v0.35.0` 已远端验证并指向 Release Head
`60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`，GitHub Pre-release ID `363770731` 已发布，
assets 为 `0`。REL-035 已最终对账并封存；规划、实施与最终对账分别见
`REL-035-V035-ALPHA-RELEASE-PLAN.md`、`REL-035-IMPLEMENTATION-TASK.md` 和
`REL-035-FINAL-RECONCILIATION.md`。

## 当前技术债与限制

- QUALITY-001：建立并逐步清理全库历史 Ruff 基线。
- Scheduler 测试曾观察到一次时序波动；不属于 SP-014B 缺陷，需独立稳定化范围。
- Docker build/run 与长期稳定性尚未正式验证。
- Knowledge 主链路、完整 Agent 产品闭环、自动 Tool Calling、完整 MCP、外部通知、Recurring Reminder 与 Web UI 未完成。
- 静态 Bearer Token 没有用户身份、RBAC 或热轮换。

CI-002 已解决：real-provider collection skip 仅作用于 `tests/real`，普通测试在混合集合中正常执行。

SP-016、SP-017、SP-018、SP-019 与 SP-020 均已完成验收并封存；ACC-016、ACC-017、ACC-018、ACC-019、ACC-020 均为 PASSED / FINAL。Latest Merged SP 与 Latest Completed SP 均为 SP-020，Current Product SP、Next Candidate SP 与 Current Governance Task 均为 None。SP-020 Feature PR #57 已 Squash Merge 为 `9ea4b72241bd855319231c09fa6b80c112a14305`，main Quality Gate `30687851816` 为 SUCCESS，并完成治理对账与封存。当前产品版本为 `0.35.0` Alpha GitHub Pre-release；REL-035 已最终对账并封存。该发布不等于 production-ready，External Notification、Recurring Reminder、Web UI、强身份/RBAC 与多租户边界仍未实现。
