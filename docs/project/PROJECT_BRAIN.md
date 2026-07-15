# AI-Lab Project Brain —— 项目大脑

> 产品基线：v0.33.0
> SP-001 / SP-001A Status：Completed
> SP-002 Status：Completed
> SP-002 Merge PR：#3（Squash Merge / APPROVED）
> SP-003 Status：Completed
> SP-003 Merge PR：#5（Squash Merge / APPROVED）
> SP-004 Status：Completed
> SP-004 Merge PR：#8（Squash Merge / APPROVED）
> SP-005 Status：Completed / Merged / Archived

## 项目使命

AI-Lab 是面向个人 CEO / 经营者的 AI Operating System 基础设施。目标是长期运行、可演化、Provider Agnostic，并从工作记录、任务、决策和知识开始支撑真实经营活动。

## 版本治理

`pyproject.toml` 的 `[project].version` 是唯一运行时产品版本来源。当前产品版本仍为 v0.33.0。SP-005 已通过 PR #10 审查并以 Squash Merge 进入 `main`，但尚未进入新的 Tag 或 Release；Reminder 与 Scheduler 默认仍关闭。

v0.33.0 基线在全新隔离 Python 3.12 环境中的最终 Windows 本地验证为 `820 passed, 27 warnings in 37.64s`；真实 DeepSeek 测试为 `5 passed in 8.37s`。这些统计不是跨平台 CI 或 GitHub Actions 结果。

SP-004 的 Windows 本地最终验证为 `847 passed, 27 warnings in 38.81s`，不是 GitHub Actions 结果。首次全量测试的 5 个错误来自 pytest 子进程继承的 SOCKS 代理环境；仅清理测试子进程代理变量后全量通过，未修改系统代理或 `.env`。

## Git 基线

```text
Repository: https://github.com/y19870785/ai-lab-os
Baseline branch: main
SP-004 integration baseline on main: 10d1534049be2d526c930c513912dc661ac41728
SP-002 merge baseline: a39dc6a2434b409d311709b08b2c0df9a555a610
Freeze tag: v0.32.4-review-baseline
SP-001 pull request: https://github.com/y19870785/ai-lab-os/pull/1
SP-001A pull request: https://github.com/y19870785/ai-lab-os/pull/2
SP-002 pull request: https://github.com/y19870785/ai-lab-os/pull/3
SP-002 merge commit: a39dc6a2434b409d311709b08b2c0df9a555a610
SP-002 merged at: 2026-07-14T18:22:14Z
SP-003 pull request: https://github.com/y19870785/ai-lab-os/pull/5
SP-003 merge baseline: ce3655ff5f7a625da6b168058873dadfc2289b5f
SP-003 merged at: 2026-07-14T19:59:33Z
SP-004 pull request: https://github.com/y19870785/ai-lab-os/pull/8
SP-004 review: APPROVED
SP-004 merge method: Squash Merge
SP-004 merge baseline: 10d1534049be2d526c930c513912dc661ac41728
SP-004 merged at: 2026-07-15T11:39:33Z
SP-005 pull request: https://github.com/y19870785/ai-lab-os/pull/10
SP-005 review: APPROVED
SP-005 merge method: Squash Merge
SP-005 merge baseline: 167b0d78f7713b1d5bfc85198c1461c7a35f63d3
SP-005 merged at: 2026-07-15T14:03:32Z
```

冻结标签保持不变。SP-001、SP-001A、SP-002、SP-003、SP-004 与 SP-005 均已完成审查并进入 `main`。SP-005 经 PR #10 以 Squash Merge 合并，审查结论为 `APPROVED`；`167b0d78f7713b1d5bfc85198c1461c7a35f63d3` 是 SP-005 合并基线，不是 PR Head。

## 状态词典

- **Implemented**：代码存在，但不代表已接入主链路。
- **Integrated**：已通过唯一 Composition Root 接入。
- **Verified**：存在自动化或真实环境验收证据。
- **Prototype**：仅用于演示或尚未达到稳定契约。
- **Disabled**：代码存在，但当前默认不启动。
- **Not Implemented**：尚未实现。

## 当前模块状态

| 模块 | 状态 | 说明 |
|---|---|---|
| Governance / RFC / ADR | Implemented | 文档数量较多，仍需持续核对实现一致性 |
| EventBus | Integrated / Verified | 由 SystemContainer 创建、启动和关闭 |
| DatabaseManager | Integrated / Verified | SP-003 已合并：管理三类 Memory SQLite 共享连接、operation-scoped lease、路径绑定、失败关闭重试与统一关闭 |
| 四层 Memory | Integrated / Verified | Session + 三个 SQLite Store；Managed/Standalone 双模式与跨重启工作记录已验证 |
| LLM Provider | Integrated / Verified | DeepSeek OpenAI Compatible 真实测试通过 |
| Embedding / Vector Provider | Implemented | Knowledge 关闭时不启动；真实组合需额外配置 |
| Knowledge | Implemented / Disabled | 默认关闭；Reindex、Chunk Persistence、Citation 与真实主链路未完成 |
| Tool Runtime | Integrated | Echo、Calculator 通过统一 ToolExecutor 注入；自动 Tool Calling 与完整 MCP 产品闭环未完成 |
| Agent Runtime | Integrated | SP-002 已合并：结构化失败、ERROR/DEGRADED 生命周期与独立错误码 |
| Workflow Runtime | Integrated | Registry 与 Executor 由 Composition Root 注入 |
| Scheduler / Reminder | Integrated / Verified / Disabled by default | SP-005 已合并；CAS claim、Occurrence 幂等与 Saga 已验证，外部通知未实现 |
| Execution TaskRuntime | Integrated | SP-002 已合并真实 Workflow retry、空计划失败与 fail-fast |
| UserTask | Integrated / Verified | SP-004 已合并：正式领域、`tasks.db`、真实 API、CEO Assistant 接入和 Legacy importer |
| Coordination | Implemented / Disabled | 默认关闭；不接入 CEO Assistant 主链路 |
| ApplicationRegistry | Integrated / Verified | 保存并查询真实 Application Instance |
| ApplicationRuntime | Integrated / Verified | 只派发已注册实例，不再创建 Provider 或默认应用 |
| CEO Assistant | Integrated / Verified | CLI、API `/work-logs`、Memory 写入和跨重启持久化已验证 |
| API `/tasks` | Integrated / Verified | 通过 UserTaskService 真实持久化；不是固定 Mock |
| API 其他通用 Task/Workflow 路由 | Prototype | 不属于 SP-004 的 UserTask 业务闭环 |

## 单一系统组合

唯一入口是 `core/system/factory.py:create_system()`，容器定义在 `core/system/container.py`。CLI、API lifespan、兼容 Bootstrap 和集成测试共用该 Factory。

默认策略：

```text
Knowledge: disabled
Scheduler: disabled
Coordination: disabled
Mock Provider: 仅显式 mock/test 模式
```

依赖和包发现同样由 `pyproject.toml` 统一管理。最小 Core、API、Real Provider、Knowledge、Test、Build、Dev 按 extras 分层；`requirements.txt` 仅是 `.[local]` 的兼容入口。正式 wheel 必须包含 API 与 CLI Python 包，但不包含 tests、data、logs 或运行数据库。

## 验证基线

```text
专项组合测试：31 passed
真实 DeepSeek：5 passed
全量测试：735 passed, 26 warnings
```

该统计来自 SP-001 的实际 pytest 输出。PR #1 已通过 ChatGPT 代码审查、合并并完成 `main` 复核。

SP-002 最终本地验证：专项故障注入 `28 passed in 1.56s`；受影响模块 `423 passed, 2 warnings in 11.62s`；全量测试 `768 passed, 26 warnings in 34.43s`。真实测试通过一次性清空测试子进程继承的 SOCKS 代理变量完成，未修改用户全局环境。合并时 GitHub 没有远端 CI checks，以上均为本地验证记录，不是 GitHub Actions 结果。

SP-005 最终 Windows 本地验证为 `888 passed, 27 warnings in 45.19s`。该统计不是 GitHub Actions 或跨平台 CI 结果。

## 当前优先级

1. SP-002 已完成并封存，统一失败契约作为后续稳定化工作的既有基线。
2. SP-003 DatabaseManager Connection Ownership 已完成并封存，SP-003 merge baseline 为 `ce3655ff5f7a625da6b168058873dadfc2289b5f`。
3. SP-004 Canonical UserTask Domain 已完成并封存，SP-004 merge baseline 为 `10d1534049be2d526c930c513912dc661ac41728`。
4. SP-005 Reminder & Scheduler Bridge 已完成并封存；SP-005 merge baseline 为 `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`。
5. 外部通知渠道、Recurring Reminder、Inbox、Knowledge Reindex/Chunk Persistence/Citation、自动 Tool Calling、完整 MCP 闭环、Coordination 主链路、UI、Database backup/restore 与 shutdown 全局请求闸门仍未完成。
6. 在主链路稳定前不推进新的产品 Phase。

## SP-003 范围边界

SP-003 只收敛 Episodic、Semantic、Decision 三类 Memory SQLite 连接所有权。Manager 是 Managed Mode 唯一 Owner，managed lease 在完整借用周期持有 per-database lock，Store 不关闭 borrowed connection；关闭失败的连接继续由 Manager 跟踪并可重试。Standalone Mode 继续使用并关闭自身连接。现有数据库路径和 Schema 不变。Knowledge SQLite Store、SchedulerPersistence 以及 shutdown 期间全局拒绝新数据库操作的闸门仍未纳入本轮。

SP-003 最终本地验证记录：专项测试 `32 passed in 1.75s`，受影响模块 `141 passed in 7.97s`，全量测试 `800 passed, 26 warnings in 41.93s`。全量首跑记录为 `795 passed, 26 warnings, 5 errors in 33.58s`，错误均来自测试进程继承 SOCKS 代理的既有 DeepSeek real 测试；在测试子进程清空代理变量后全部通过，未修改用户全局环境。该结果不是 GitHub Actions 记录。
