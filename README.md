# AI-Lab

个人级 AI 操作系统（Personal AI Operating System）。

## 定位

AI-Lab 的目标不是开发单一应用，而是建立一个可持续扩展的 AI Agent 平台。
未来所有 AI 应用均基于 AI-Lab。

**AI 辅助决策，不替代人的最终判断。**

当前目标产品基线为 **v0.33.0**。`pyproject.toml` 的 `[project].version` 是唯一运行时产品版本来源，`core.__version__`、CLI 与 API 均从 package metadata 或该来源派生。

## 架构

**SP-001：Single Composition Root 已完成并合并。** CLI、FastAPI lifespan、兼容 Bootstrap 与集成测试统一通过 `core.system.create_system()` 创建一套 `SystemContainer`。该实现已通过架构审查与合并后复核，现为 `main` 的稳定化基线。

**SP-002：Failure Semantics & Observability 已完成并通过 PR #3 以 Squash Merge 合并到 `main`。** `FailureInfo` 已成为 Agent、Task、Scheduler、API、失败事件与 System Health 的统一失败契约。首轮审查发现的 Agent 缺失依赖静默跳过、HTTP 200 携带错误状态、Memory 健康无法恢复和 Health 聚合错误均已修复。合并基线为 `a39dc6a2434b409d311709b08b2c0df9a555a610`，审查结论为 `APPROVED`。

**SP-003：DatabaseManager Connection Ownership 已完成，并通过 PR #5 以 Squash Merge 合并到 `main`。** Composition Root 将同一个 `DatabaseManager` 注入 Episodic、Semantic、Decision Store；Manager 是共享连接唯一 Owner。Managed lease 在完整借用周期持有对应数据库锁，`close()`/`close_all()` 会等待活跃借用，关闭失败的连接继续由 Manager 跟踪并可重试。现有 `sqlite_dir/*.db` 路径与 Schema 保持不变，Standalone Store 仍保留独立运行能力。SP-003 merge baseline 为 `ce3655ff5f7a625da6b168058873dadfc2289b5f`。

SP-003A 已完成合并后状态对账。v0.33.0 汇总 SP-001 至 SP-003 的稳定化成果；`v0.32.4-review-baseline` 继续作为历史冻结标签保留，SP-004 尚未开始。

采用十层架构（v0.22.0）：

```
┌───────────────────────────────────────────────────────────┐
│            Governance Layer（治理层）                       │
│  开发策略 · Agent 策略 · 知识策略 · 模型策略 · 版本策略     │
├───────────────────────────────────────────────────────────┤
│            Application Layer（业务应用层）                  │
│  Investment Office · Enterprise AI · Quotation System      │
├───────────────────────────────────────────────────────────┤
│              Task Runtime（任务编排层）                     │
│  TaskManager · Planner · DependencyResolver · Checkpoint   │
├───────────────────────────────────────────────────────────┤
│            Scheduler Runtime（调度层）                     │
│  TriggerEngine · JobExecutor · Persistence                 │
├───────────────────────────────────────────────────────────┤
│            Workflow Engine（工作流层）                     │
│  StateMachine · Checkpoint · Planner · Executor            │
├───────────────────────────────────────────────────────────┤
│              Agent Runtime（智能 Agent 层）                 │
│  Lifecycle · ContextBuilder · Executor · Registry          │
├───────────────────────────────────────────────────────────┤
│            Knowledge Layer（知识系统层）                    │
│  Ingestion Pipeline · Chunking · Hybrid Retrieval · Rank   │
├───────────────────────────────────────────────────────────┤
│            Provider Layer（模型抽象层）                     │
│  LLM · Embedding · Vector · Storage（Protocol + Mock）     │
├───────────────────────────────────────────────────────────┤
│              Tool Runtime（工具执行层）                     │
│  Sandbox · Permissions · Audit · Metrics · MCP Adapter     │
├───────────────────────────────────────────────────────────┤
│              Memory Layer（记忆系统层）                     │
│  Session · Episodic · Semantic · Decision（四层）          │
│  Consolidation Engine（Importance / Decay / Policy）       │
├───────────────────────────────────────────────────────────┤
│              Core Layer（基础能力层）                       │
│  配置 · 日志 · 消息总线 · 数据库                            │
└───────────────────────────────────────────────────────────┘
```

## 核心理念

| AI 负责 | 用户负责 |
| --- | --- |
| 信息收集 · 数据整理 | 最终决策 |
| 分析 · 提醒 | 业务判断 |
| 自动化执行 | 重要审批 |

## 当前阶段

当前处于 **Phase 4 —— AI OS Runtime**（v0.22.0）。

| Phase | 内容 | 状态 |
| --- | --- | --- |
| 1.1 - 1.6 | Foundation Phase 架构设计 | ✅ |
| 2.1 - 2.8 | Core + Memory Implementation | ✅ |
| 3.0 - 3.4 | Provider / Knowledge / Agent / Tool / MCP | ✅ |
| 4.0 | Workflow Engine | ✅ |
| 4.1 | Scheduler Runtime | ✅ |
| 4.2 | Task Runtime | ✅ |
| 4.3 | Multi-Agent Coordination | ⏳ |
| 5.0 | Real LLM Integration + Application Layer | ⏳ |

## 项目结构

```
AI-Lab/
├── docs/
│   ├── governance/     # 治理体系（6 个策略文件）
│   ├── rfc/            # 架构设计文档（12 篇）
│   ├── adr/            # 架构决策记录（23 篇）
│   └── project/        # 项目健康 / 路线图 / 里程碑
├── core/
│   ├── bus/            # 消息总线（Event Bus + Task Queue）
│   ├── database/       # 数据库管理（Connection Pool + Migration）
│   ├── memory/         # 记忆系统（Session / Episodic / Semantic / Decision）
│   ├── providers/      # Provider Layer（LLM / Embedding / Vector / Storage）
│   ├── knowledge/      # 知识系统（Ingestion / Chunking / Retrieval / Ranking）
│   ├── agents/         # Agent Runtime（Lifecycle / ContextBuilder / Executor）
│   ├── tools/          # Tool Runtime（Sandbox / Permissions / MCP Adapter）
│   ├── workflow/       # Workflow Engine（StateMachine / Checkpoint / Planner）
│   ├── scheduler/      # Scheduler Runtime（Trigger / Job / Persistence）
│   ├── task/           # Task Runtime（编排 / 依赖 / 检查点）
│   ├── system/         # 唯一 Composition Root + SystemContainer + Settings
│   ├── logging.py      # 日志系统（Trace ID / Agent ID 上下文）
│   └── config.py       # 配置管理
├── tests/
│   ├── core/           # 各模块单元测试
│   └── integration/    # 端到端集成测试
├── applications/       # 业务应用（预留）
├── prompts/            # Prompt 模板管理（预留）
├── config/             # 配置模板
└── logs/               # 运行日志
```

## 开发规范

- **文档驱动**：重大设计先写 RFC，架构决策记录 ADR
- **模型不可知**：业务层不绑定具体模型
- **配置驱动**：所有行为由配置控制，不硬编码
- **详见**：[开发策略](docs/governance/DEVELOPMENT_POLICY.md)

## 技术栈

- Python 3.10+
- Pydantic + YAML + 环境变量（配置）
- SQLite（存储）+ Chroma / Qdrant（向量，预留）
- asyncio（进程内通信）
- 735 个测试通过，26 个既有 warning，零失败

---

> 当前稳定化基线：SP-001 completed | Main commit：`0a36e250ab8382af6cf3ab3068e432aa69ba3399` | 验证：735 passed
