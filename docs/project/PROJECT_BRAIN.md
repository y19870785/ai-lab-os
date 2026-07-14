# AI-Lab Project Brain —— 项目大脑

> 版本基线：v0.32.4
> 当前工作：SP-001 Single Composition Root
> 状态：独立分支验证通过，等待 Pull Request 审查，尚未合并

## 项目使命

AI-Lab 是面向个人 CEO / 经营者的 AI Operating System 基础设施。目标是长期运行、可演化、Provider Agnostic，并从工作记录、任务、决策和知识开始支撑真实经营活动。

## Git 基线

```text
Repository: https://github.com/y19870785/ai-lab-os
Baseline branch: main
Base commit: a6f2b62b867a4ed1a244db7d74f2dbb25195f395
Freeze tag: v0.32.4-review-baseline
Working branch: fix/sp-001-single-composition-root
```

冻结标签保持不变。SP-001 必须通过 PR 审查后才能合并到 `main`。

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
| Agent Runtime | Integrated | 缺少 LLM/Memory/ToolExecutor 时显式失败 |
| Workflow Runtime | Integrated | Registry 与 Executor 由 Composition Root 注入 |
| Scheduler Runtime | Disabled | 可显式启用，生命周期测试通过 |
| Execution TaskRuntime | Integrated | 依赖统一 WorkflowRuntime；完整 Retry 技术债未处理 |
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

该统计来自 SP-001 分支实际 pytest 输出。PR 尚未经过 ChatGPT 代码审查，因此不得写成“SP-001 完成”。

## 当前优先级

1. 创建 SP-001 Pull Request 并审查真实 Diff。
2. 审查通过后合并并复核 `main`。
3. 后续 SP-003 处理 DatabaseManager Connection Ownership。
4. 在主链路稳定前不推进新的产品 Phase。
