# AI-Lab Project Brain —— 项目大脑

> 冻结版本：v0.32.4 | 日期：2026-07-14
> 状态：开发暂停，等待独立架构审查

---

## 项目使命

AI-Lab 是一个面向**个人 CEO / 经营者**的 AI Operating System（AI 操作系统）基础设施。

不是聊天机器人，不是 RAG 演示，不是 Agent 玩具。

最终目标：让经营者拥有一套可以**长期运行、可演化、不受具体模型绑定的**个人 AI 工作系统。从工作记录、任务管理、决策追踪、知识检索开始，逐步覆盖日常经营所需的全部信息处理。

---

## 当前产品定位

| 维度 | 状态 |
|---|---|
| Framework 完成度 | 约 70%（十层基础架构已完成） |
| CEO Assistant | Alpha 阶段，可交互式运行 |
| 生产就绪 | 否（Alpha 级别） |
| 多租户 / 多用户 | 不支持 |
| 外部部署 | 仅本地 Windows |

当前唯一正在运行的真实业务应用：**CEO Assistant（超哥的个人工作总控助手）**。

支持功能：
- 工作记录（Work Log）
- 待办任务（Task）
- 决策记录（Decision）
- 知识问答（Knowledge QA）
- 每日简报（Daily Brief）

---

## 当前版本

```
版本：v0.32.4
日期：2026-07-14
Git：无 commit（仓库尚未初始化 git）
```

---

## 已完成能力（按实际代码）

| 层级 | 模块 | 状态 |
|---|---|---|
| Governance | 治理策略 + RFC/ADR 体系 | ✅ 完整 |
| Core | EventBus / Logging / Config / Lifecycle | ✅ 完整 |
| Database | SQLite 连接池 / Migration | ✅ 完整 |
| Memory | Session / Episodic / Semantic / Decision | ✅ 完整 |
| Provider | LLM / Embedding / Vector / Storage 协议 | ✅ 协议完整 |
| Provider | DeepSeek (OpenAI Compatible) 真实接入 | ✅ 可用 |
| Provider | SentenceTransformer 本地 Embedding | ✅ 可用 |
| Provider | Chroma Vector Store | ✅ 可用 |
| Knowledge | Ingestion Pipeline / Chunking / Retrieval / Ranking | ✅ 完整 |
| Agent | Runtime / ContextBuilder / Lifecycle / Registry | ✅ 完整 |
| Tool | Runtime / Registry / Sandbox / Permissions / Builtins | ✅ 完整 |
| MCP | Adapter / Client / Discovery | ✅ 完整 |
| Workflow | Engine / State Machine / Checkpoint / Planner | ✅ 完整 |
| Scheduler | Cron / Interval / OneShot Trigger + SQLite Persistence | ✅ 完整 |
| Task | Runtime / Dependency / Checkpoint / Recovery | ✅ 完整 |
| Coordination | Multi-Agent Orchestrator / MessageBus / Delegation | ✅ 完整 |
| Workspace | 数据隔离 | ✅ 完整 |
| Application | Runtime / Registry / Config / Manifest | ✅ 完整 |
| CEO Assistant | 交互式 CLI + API | ✅ Alpha 可用 |

---

## 当前正在解决的问题

v0.32.4 刚刚完成以下修复（2026-07-14）：

1. **CLI 交互式启动**：`start.bat` 双击后直接进入交互对话，不再停在帮助页
2. **Provider 模式统一检测**：`real` / `mock` / `invalid` 三种状态，所有入口一致
3. **DeepSeek v4-flash 接入**：CLI 和 API 双链路均已接通真实 LLM
4. **API 模式 LLM 接入**：`ApplicationRuntime.execute()` 在没有 Agent Runtime 时懒初始化 LLM

---

## 当前禁止事项

- 不新增架构层
- 不开发插件市场
- 不开发 Persona 系统
- 不开发企业微信
- 不开发报价系统
- 不开发 Investment Office
- 不继续 Framework First 堆层
- 不推翻已有架构

---

## 核心架构原则

1. **Application First**：先有真实业务需求，再抽象框架能力
2. **Business Driven Framework**：框架从业务中生长，不为架构而架构
3. **Provider Agnostic**：不绑定具体模型 / 向量库 / 存储
4. **Protocol First**：接口先行，实现可替换
5. **Event Driven**：所有模块通过 EventBus 通信
6. **Manager / Runtime 作为统一入口**：禁止业务层直接访问 Store / Provider
7. **Workspace 隔离**：不同业务数据物理隔离
8. **Decision Memory 独立**：不与 Episodic / Semantic 混淆
9. **不保存模型私有思维链**：不记录 reasoning_content
10. **Mock 与 Real 明确区分**：单元测试用 Mock，集成测试用 Real
11. **测试统计必须引用 pytest 原始结果**：禁止人工估算
12. **全量测试存在失败时 Gate 不得 PASS**

---

## 下一步状态

```
当前状态：开发暂停
下一步动作：使用全新 Codex GPT-5.6 进行独立全面架构审查
审查完成后：根据审查结果决定是否继续 v0.33.0 还是重构
```
