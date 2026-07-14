# AI-Lab Project Brain —— 项目大脑

> 版本基线：v0.32.4
> SP-001 / SP-001A Status：Completed
> SP-002 Status：Implemented on branch / Awaiting review
> SP-002 Branch：`fix/sp-002-failure-semantics`

## 项目使命

AI-Lab 是面向个人 CEO / 经营者的 AI Operating System 基础设施。目标是长期运行、可演化、Provider Agnostic，并从工作记录、任务、决策和知识开始支撑真实经营活动。

## Git 基线

```text
Repository: https://github.com/y19870785/ai-lab-os
Baseline branch: main
Base commit: a77e0436f7583531ff2635f3c5422d7a00fe69b5
Freeze tag: v0.32.4-review-baseline
SP-001 pull request: https://github.com/y19870785/ai-lab-os/pull/1
SP-001A pull request: https://github.com/y19870785/ai-lab-os/pull/2
```

冻结标签保持不变。SP-001 与 SP-001A 已完成审查、合并和复核。SP-002 从 `a77e0436f7583531ff2635f3c5422d7a00fe69b5` 创建独立分支，当前等待代码审查，尚未合并。

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
| DatabaseManager | Implemented | 未注入 Memory Store；共享连接所有权留给 SP-003 |
| 四层 Memory | Integrated / Verified | Session + 三个独立 SQLite Store，跨重启工作记录已验证 |
| LLM Provider | Integrated / Verified | DeepSeek OpenAI Compatible 真实测试通过 |
| Embedding / Vector Provider | Implemented | Knowledge 关闭时不启动；真实组合需额外配置 |
| Knowledge | Disabled | 可显式启用；Reindex、Chunk 持久化等仍有限制 |
| Tool Runtime | Integrated | Echo、Calculator 通过统一 ToolExecutor 注入 |
| Agent Runtime | Integrated | SP-002 分支已实现结构化失败、ERROR/DEGRADED 生命周期与独立错误码 |
| Workflow Runtime | Integrated | Registry 与 Executor 由 Composition Root 注入 |
| Scheduler Runtime | Disabled | 可显式启用；SP-002 分支已实现 tick 失败观测、后台 task 跟踪和 shutdown 收集 |
| Execution TaskRuntime | Integrated | SP-002 分支已实现真实 Workflow retry、空计划失败与 fail-fast |
| Coordination | Disabled | 本轮不接入 CEO Assistant 主链路 |
| ApplicationRegistry | Integrated / Verified | 保存并查询真实 Application Instance |
| ApplicationRuntime | Integrated / Verified | 只派发已注册实例，不再创建 Provider 或默认应用 |
| CEO Assistant | Integrated / Verified | CLI、API `/work-logs`、Memory 写入和跨重启持久化已验证 |
| API 通用 Task/Workflow 路由 | Prototype | 不属于 SP-001 的真实业务闭环 |

## 单一系统组合

唯一入口是 `core/system/factory.py:create_system()`，容器定义在 `core/system/container.py`。CLI、API lifespan、兼容 Bootstrap 和集成测试共用该 Factory。

默认策略：

```text
Knowledge: disabled
Scheduler: disabled
Coordination: disabled
Mock Provider: 仅显式 mock/test 模式
```

## 验证基线

```text
专项组合测试：31 passed
真实 DeepSeek：5 passed
全量测试：735 passed, 26 warnings
```

该统计来自 SP-001 的实际 pytest 输出。PR #1 已通过 ChatGPT 代码审查、合并并完成 `main` 复核。

SP-002 分支当前验证：专项故障注入 `24 passed`；DeepSeek 真实测试 `5 passed in 9.19s`；全量测试 `759 passed, 26 warnings in 33.59s`。真实测试通过一次性清空测试子进程继承的 SOCKS 代理变量完成，未修改用户全局环境。当前状态仍不等于 Completed。

## 当前优先级

1. SP-002 当前仅在独立分支实现，必须创建 Draft PR 并等待 ChatGPT 审查。
2. 未经明确 APPROVED 不得合并，也不得将状态写为 Completed。
3. SP-003 继续处理 DatabaseManager Connection Ownership。
4. 在主链路稳定前不推进新的产品 Phase。
