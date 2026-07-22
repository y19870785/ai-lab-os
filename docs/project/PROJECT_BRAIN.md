# AI-Lab Project Brain —— 项目大脑

> Product Version: v0.34.0
> Last Completed SP: SP-016
> Current SP: SP-017
> Current Governance Task: None
> Next Candidate SP: SP-018
> Next Candidate Direction: Structured Work Log Query & Context Linking
> SP-016 Status: APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / COMPLETED / ARCHIVED
> ACC-016 Status: PASSED / FINAL
> SP-017 Status: APPROVED_FOR_IMPLEMENTATION / IN_PROGRESS
> SP-017 Design: RFC-026 Adopted; ADR-056 and ADR-057 Accepted
> Release Stage: v0.34.0 Alpha / RELEASE_AUTHORIZED
> Verified Release Baseline: `22f88d1da962fb436c48c19e5343fad8bf62f5f6` / Quality Gate run `29855987444`
> SP-015 Base Commit: `57444274abd4e568a6af72b218d50290de563654`
> SP-015 Branch: `chore/sp-015-release-governance-consolidation`
> SP-015 Status: APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED
> SP-015A Status: APPROVED / MERGED / RECONCILED / ARCHIVED
> SP-015R Status: APPROVED / MERGED / RECONCILED / ARCHIVED
> Authorized Tag: v0.34.0
> GitHub Release Type: Pre-release

`Verified Release Baseline` 是最终发布提交之前经独立 main Quality Gate 验证的历史基线，不声明等于包含本文件的当前提交。当前 HEAD、Tag 与 GitHub Release 的存在性、目标、URL 和时间通过 Git/GitHub 查询；仓库根目录 [project_state.json](../../project_state.json) 记录稳定的项目与发布授权状态。

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

## 永久架构事实

### Canonical Composition Root

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
| Waiting-For | 独立 canonical domain、`followups.db`、API/CLI 与 append-only history 已通过人工验收并封存 |
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
| UserTask / Daily Agenda / Unified Inbox | Integrated / Verified | Agenda 已支持可选来源组合 |
| Waiting-For | Integrated / Verified / Manual acceptance passed | SP-016 completed / archived |
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

## v0.34.0 Alpha / Release Authorized

本 Alpha 版本收口 UserTask、Reminder Core、Reminder Management、Intent Safety、Daily Agenda、Unified Inbox、Capture-to-Action、统一 Composition Root 和治理一致性。

明确不包含：

- 外部通知与 Recurring Reminder；
- Web UI；
- 完整 Knowledge 主链路；
- 用户身份、OAuth/JWT/RBAC 与强多租户；
- 企业级部署或生产可用性承诺。

SP-015R 已合并、通过 main Quality Gate 并封存；Owner 与 ChatGPT 已授权 Tag `v0.34.0` 和 GitHub Pre-release。Tag 是否存在及其目标、Release 发布状态、URL 与时间均以 GitHub Tags and GitHub Releases 为权威来源，仓库不维护这些外部事实的实时布尔镜像。

## 当前技术债与限制

- QUALITY-001：建立并逐步清理全库历史 Ruff 基线。
- Scheduler 测试曾观察到一次时序波动；不属于 SP-014B 缺陷，需独立稳定化范围。
- Docker build/run 与长期稳定性尚未正式验证。
- Knowledge 主链路、完整 Agent 产品闭环、自动 Tool Calling、完整 MCP、外部通知、Recurring Reminder 与 Web UI 未完成。
- 静态 Bearer Token 没有用户身份、RBAC 或热轮换。

CI-002 已解决：real-provider collection skip 仅作用于 `tests/real`，普通测试在混合集合中正常执行。

SP-016 Canonical Waiting-For Domain & Agenda Closure 已完成人工验收并封存，ACC-016 为 PASSED / FINAL；Current Product SP 为 SP-017，Current Governance Task 为 None。SP-017 Follow-up Interaction & Capture Closure 已获准实施并处于 IN_PROGRESS，RFC-026 为 Adopted，ADR-056 与 ADR-057 为 Accepted；尚未标记 completed、verified 或 accepted。SP-018 与 SP-019 仅为候选，均未批准、未启动。
