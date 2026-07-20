# AI-Lab Project Brain —— 项目大脑

> Product Version: v0.34.0
> Last Completed SP: SP-015
> Current SP: None
> Next Candidate SP: SP-016
> Next Candidate Direction: Follow-up & Waiting-For Workflow
> Release Stage: v0.34.0 Alpha Candidate / VERIFIED / UNPUBLISHED / READY_FOR_RELEASE_AUTHORIZATION
> Current main: `712b6f6e3d233d008d22098bec4a8f317af603c3`
> SP-015 Base Commit: `57444274abd4e568a6af72b218d50290de563654`
> SP-015 Branch: `chore/sp-015-release-governance-consolidation`
> SP-015 Status: APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED
> SP-015A Status: APPROVED / MERGED / RECONCILED / ARCHIVED
> SP-015R Status: IN_PROGRESS / DRAFT_PR_OPEN
> v0.34.0 Tag: NOT_CREATED
> v0.34.0 GitHub Release: NOT_CREATED

`Current main` 记录 SP-015 合并并通过 post-merge acceptance 的远端 `main` 基线。机器可读实时状态以仓库根目录 [project_state.json](../../project_state.json) 为唯一来源。

## 项目使命

AI-Lab 是面向个人经营者和本地工作流的 AI Operating System 基础设施。它以长期运行、可演化、Provider Agnostic 为设计目标，从任务、提醒、工作记录、日程、收件箱和知识基础设施支撑真实经营活动。

AI 可以收集、整理、分析和提醒；最终业务判断与重要审批仍由用户负责。

## 治理事实来源

| 载体 | 职责 |
|---|---|
| `project_state.json` | 唯一机器可读实时状态：版本、main 基线、SP、Quality Gate、技术债与 Release 状态 |
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
| Daily Agenda | 已集成并通过手工验收；统一 UserTask、Reminder 与 Work Log 只读视图 |
| Unified Inbox | 已集成并通过 ACC-014；Capture-to-Action 与持久化 resolution claim |
| API Security | Bearer Token 与 CORS allowlist 已集成；尚无用户身份和 RBAC |

历史 PR、Head、merge commit、合并时间和各 SP 状态集中保存在 `project_state.json`，不在本文件重复维护完整流水账。

## 当前模块状态

| 模块 | 状态 | 边界 |
|---|---|---|
| Governance | Integrated / SP-015 and SP-015A archived; SP-015R Draft open | 统一机器状态、版本、文档职责与一致性测试 |
| EventBus / Database / Memory | Integrated / Verified | 本地持久化主链路 |
| Provider | Integrated / Verified | Mock 路径属于普通门禁；真实 Provider 需单独授权 |
| Knowledge | Implemented / Disabled | 真实主链路、reindex、chunk persistence、citation 未完成 |
| Agent / Tool / MCP | Integrated foundation | 完整 Agent 产品闭环、自动 Tool Calling 与完整 MCP 闭环未完成 |
| Workflow / Task Runtime | Integrated / Verified | 运行时和失败语义已验证 |
| Scheduler / Reminder | Integrated / Verified / Disabled by default | 外部通知与 Recurring Reminder 未实现 |
| UserTask / Daily Agenda / Unified Inbox | Integrated / Verified | 当前 v0.34.0 Alpha 候选核心能力 |
| Coordination | Implemented / Disabled | 未接入 CEO Assistant 主链路 |
| CEO Assistant / API / CLI | Integrated / Verified / Alpha | local-first，不是 production-ready 产品 |

## 验证基线

当前正式 Quality Gate 事实来自 GitHub Actions run `29749469117`：

```text
Environment: ubuntu-latest / Python 3.12
Ruff: SUCCESS (changed Python files only)
pytest (non-real): 1163 passed, 6 skipped, 27 warnings
tests/real: explicitly excluded
```

历史本地测试只能作为对应时间和环境的记录，不替代当前 GitHub Quality Gate；真实 Provider 结果也不由普通门禁推导。

## v0.34.0 Alpha Candidate

本候选版本收口 UserTask、Reminder Core、Reminder Management、Intent Safety、Daily Agenda、Unified Inbox、Capture-to-Action、统一 Composition Root 和治理一致性。

明确不包含：

- 外部通知与 Recurring Reminder；
- Web UI；
- 完整 Knowledge 主链路；
- 用户身份、OAuth/JWT/RBAC 与强多租户；
- 企业级部署或生产可用性承诺。

仓库已有历史 `v0.33.0` Tag；v0.34.0 Alpha Candidate 已验证且未发布，当前已进入 release authorization readiness。Tag 和 GitHub Release 尚未创建，必须等待 SP-015R 合并、main Quality Gate 和 Owner/ChatGPT 独立发布授权。

## 当前技术债与限制

- CI-002：收窄 `tests/real/conftest.py` collection hook 作用域。
- QUALITY-001：建立并逐步清理全库历史 Ruff 基线。
- Scheduler 测试曾观察到一次时序波动；不属于 SP-014B 缺陷，需独立稳定化范围。
- Docker build/run 与长期稳定性尚未正式验证。
- Knowledge 主链路、完整 Agent 产品闭环、自动 Tool Calling、完整 MCP、外部通知、Recurring Reminder 与 Web UI 未完成。
- 静态 Bearer Token 没有用户身份、RBAC 或热轮换。

SP-016 Follow-up & Waiting-For Workflow、SP-017 Recurring Reminder、SP-018 Minimal Web Console 与 SP-019 Knowledge Main Path 仅为 Roadmap 候选，未批准、未启动。SP-015A 已合并并封存；SP-015R 当前为 IN_PROGRESS / DRAFT_PR_OPEN。
