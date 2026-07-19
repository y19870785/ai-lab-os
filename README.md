# AI-Lab

个人级 AI 操作系统（Personal AI Operating System）。

## 定位

AI-Lab 的目标不是开发单一应用，而是建立一个可持续扩展的 AI Agent 平台。
未来所有 AI 应用均基于 AI-Lab。

**AI 辅助决策，不替代人的最终判断。**

当前目标产品基线为 **v0.33.0**。`pyproject.toml` 的 `[project].version` 是唯一运行时产品版本来源，`core.__version__`、CLI 与 API 均从 package metadata 或该来源派生。

> **SP-010 Reminder Inbox** 已通过 PR #21 审查并以 Squash Merge 进入 `main`，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。用户可通过 API、CLI 与确定性自然语言查询浏览持久化提醒；外部通知、Recurring Reminder 与 Web UI 仍未实现。产品版本保持 `0.33.0`，未创建新 Tag 或 Release。

> **SP-011 Reminder Management Closure** 已通过 PR #23 审查并以 Squash Commit `5c4b442b2b5c7f934ac381020ba8b310976d5d3a` 进入 `main`，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。统一管理服务为 API、CLI 与 CEO Assistant 提供详情、取消、改期、歧义解析和 workspace 校验；`view=pending` 表示未来 scheduled/retrying；确定性 Reminder 响应不附带 LLM/Mock 噪音；CLI 自主管理 UTF-8 输出边界。RFC-021 已 Adopted，ADR-043/044/045 已 Accepted。手工验收记录为 Reminder Core PASSED、Natural-language Reminder UX CONDITIONALLY PASSED。

> **SP-013 Daily Agenda** 已完成最终验收，状态为 APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED。统一只读日程视图覆盖 API、CLI 与 CEO Assistant；SP-013B 通过 PR #29 修复了 CLI 默认 workspace 边界。当前 `main` 为 `23b54be4bd3030c564c2e1a0325eaf36199357fe`，产品版本仍为 `0.33.0`，未创建新 Tag 或 Release。

> **CI-001 Quality Gate** 已通过 PR #30 合入。Pull Request、`main` push 与手动触发均使用 Python 3.12；Ruff 只检查本次变更的 Python 文件，pytest 显式排除 `tests/real`。这不代表全库 Ruff 或 real-provider 测试已通过。

> **SP-014B Chinese Numeral Reminder Time Compatibility** 当前修复分支仅扩展确定性 Reminder Parser：在 `今天/明天` 与明确 `上午/下午/晚上` 组合中，小时支持中文数字 `一` 至 `十二`，并继续复用既有分钟、时区、UTC、过去时间和幂等链路。不支持后天、星期、相对/模糊时间、中文分钟、Recurring Reminder 或 LLM 时间解析。ACC-014 仍保持最近一次正式验收的 FAILED 结论，等待独立复验；版本仍为 `0.33.0`。

## 架构

**SP-001：Single Composition Root 已完成并合并。** CLI、FastAPI lifespan、兼容 Bootstrap 与集成测试统一通过 `core.system.create_system()` 创建一套 `SystemContainer`。该实现已通过架构审查与合并后复核，现为 `main` 的稳定化基线。

**SP-002：Failure Semantics & Observability 已完成并通过 PR #3 以 Squash Merge 合并到 `main`。** `FailureInfo` 已成为 Agent、Task、Scheduler、API、失败事件与 System Health 的统一失败契约。首轮审查发现的 Agent 缺失依赖静默跳过、HTTP 200 携带错误状态、Memory 健康无法恢复和 Health 聚合错误均已修复。合并基线为 `a39dc6a2434b409d311709b08b2c0df9a555a610`，审查结论为 `APPROVED`。

**SP-003：DatabaseManager Connection Ownership 已完成，并通过 PR #5 以 Squash Merge 合并到 `main`。** Composition Root 将同一个 `DatabaseManager` 注入 Episodic、Semantic、Decision Store；Manager 是共享连接唯一 Owner。Managed lease 在完整借用周期持有对应数据库锁，`close()`/`close_all()` 会等待活跃借用，关闭失败的连接继续由 Manager 跟踪并可重试。现有 `sqlite_dir/*.db` 路径与 Schema 保持不变，Standalone Store 仍保留独立运行能力。SP-003 merge baseline 为 `ce3655ff5f7a625da6b168058873dadfc2289b5f`。

**SP-004：Canonical UserTask Domain 已完成审查并通过 PR #8 以 Squash Merge 合并到 `main`。** 合并提交为 `10d1534049be2d526c930c513912dc661ac41728`，审查结论为 `APPROVED`。正式 UserTask 领域、`tasks.db` 持久化、真实 `/tasks` API、CEO Assistant 接入和显式 Legacy Decision Memory importer 已进入主分支。

当前产品版本仍为 v0.33.0。SP-005 Reminder & Scheduler Bridge 已通过 PR #10 审查，并以 Squash Merge 合并到 `main`；合并提交为 `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`，审查结论为 `APPROVED`，合并时间为 `2026-07-15T14:03:32Z`。持久化 Reminder/Occurrence、SQLite CAS claim、One-shot terminal 语义、Action Handler、跨库 Saga/reconciliation、UserTask 终态联动和真实 Reminder API 已进入主分支，但默认仍关闭。该能力属于 `post-v0.33.0 main`，尚未进入新的 Tag 或 Release；外部通知渠道、Recurring Reminder、Inbox 与 UI 仍未实现。

SP-005 的 Windows 隔离 Python 3.12 本地最终验证为 `888 passed, 27 warnings in 45.19s`，不是 GitHub Actions 或跨平台 CI 结果。

## 安装契约

`pyproject.toml` 同时是版本与依赖的唯一权威来源：

```powershell
# 最小 Core 运行环境
python -m pip install -e .

# 本地开发、API、真实 Provider、测试与构建验收
python -m pip install -e ".[local]"
```

`requirements.txt` 仅保留为 `[local]` extra 的兼容安装入口，不再维护第二份依赖列表。Knowledge 的 Chroma 与 SentenceTransformer 仍是显式可选依赖，不会进入最小 Core 或默认本地安装。

当前统一为十一层架构；Coordination 作为独立层存在：

```
┌───────────────────────────────────────────────────────────┐
│            Governance Layer（治理层）                       │
│  开发策略 · Agent 策略 · 知识策略 · 模型策略 · 版本策略     │
├───────────────────────────────────────────────────────────┤
│            Application Layer（业务应用层）                  │
│  Investment Office · Enterprise AI · Quotation System      │
├───────────────────────────────────────────────────────────┤
│           Coordination Layer（协作协调层）                  │
│  Team Registry · Planner · Orchestrator · Communication    │
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
| 3.0 - 3.4 | Provider / Knowledge / Agent / Tool / MCP | Implemented；Knowledge 默认 Disabled，自动 Tool Calling 未完成 |
| 4.0 | Workflow Engine | Integrated |
| 4.1 / SP-005 | Scheduler + Reminder | Integrated / Verified / Disabled by default；外部通知未实现 |
| 4.2 | Task Runtime | Integrated |
| 4.3 | Multi-Agent Coordination | Implemented / Disabled；未接入 CEO Assistant 主链路 |
| 5.0 | Real LLM Integration + Application Layer | Integrated；CEO Assistant 为 Alpha |

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

- Python >=3.11
- Pydantic + YAML + 环境变量（配置）
- SQLite（存储）+ Chroma / Qdrant（向量，预留）
- asyncio（进程内通信）
- 当前验证统计以 `docs/project/PROJECT_HEALTH.md` 为准；正式普通门禁来自 GitHub Quality Gate，历史本地记录会单独标注

---

> 当前产品版本：`v0.33.0`。`main` 已包含 SP-004～SP-013B 的 post-v0.33.0 工作，但尚未创建新的 Tag、Release 或版本号。

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 System Lifecycle Admission Gate: APPROVED / MERGED / RECONCILED / ARCHIVED. PR #14 的 Approved Head 为 `527ecba0ee411edb260b5bbcfdfc24dfa22a5bb4`，Squash Merge Commit 为 `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`，合并时间为 `2026-07-16T10:08:47Z`，产品版本保持 `0.33.0`。

> SP-008 Internal Work Admission Boundary: **APPROVED / MERGED / RECONCILED / ARCHIVED**。PR #16 以 Approved Head `536d1563baaecf5d50eeefc93dfdb0dbbfe3c659` 通过审查，Squash Commit `1858d4991379058948559cc96e2672df44e42b67` 于 `2026-07-16T11:06:29Z` 进入 main。API 与内部入口共享同一生命周期真相；RFC-018 已 Adopted，ADR-037/038 已 Accepted。

> SP-008 合并前 Windows 本地 Python 3.12 验证：`977 passed, 27 warnings in 49.17s`，零失败、零错误；该结果是历史本地记录，不是 GitHub Actions 或跨平台 CI 健康保证。产品版本仍为 `0.33.0`，未创建新 Tag 或 Release。

> **SP-009：APPROVED / MERGED / RECONCILED / ARCHIVED。** PR #19 以 Squash Merge 合入 `main`，merge commit 为 `b1274d066cbc01053144cba8d5654a5f8c8a21da`。受支持的自然语言提醒已接入真实 UserTask、Reminder、Scheduler Job、Occurrence 和站内状态查询，成为首个用户可验收的持久化产品切片。Task 的截止时间与 Reminder 调度仍是独立概念；仅支持今天/明天的确定性时间子集，外部通知、Inbox、Recurring Reminder、复杂日期和 Web UI 尚未实现。产品版本保持 `0.33.0`，未创建 Tag 或 Release。

> **SP-012 Intent Safety and Reminder Query UX** 已通过 PR #25 审查并以 Squash Commit `d550ab8757b50e4d12587d5e71a0058089bd3821` 进入 `main`，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。其查询兼容性已由 SP-013 场景 H 实际验证：“今天都有什么事？”保持 `reminder_list/read` 且无写入；不虚构独立 SP-012 全量手工验收。

> **SP-014** 已通过 PR #32 合并；最近一次 ACC-014 记录为 A～J PASSED、K FAILED、L NOT_EXECUTED_AFTER_CORE_FAILURE。SP-014B 只修复场景 K 暴露的中文小时兼容性，不预先改变该验收结论。
