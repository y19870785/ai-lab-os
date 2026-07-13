# AI-Lab 项目结构

```
AI-Lab/
├── core/                         # 核心引擎
│   ├── bus/                      # Message Bus（Event + Task Queue）
│   ├── database/                 # 数据库管理（SQLite + Migration）
│   ├── logging.py                # 日志系统（JSON + TraceID）
│   ├── config.py                 # 配置管理
│   ├── memory/                   # 四层记忆系统
│   │   ├── models.py             # MemoryItem / MemoryQuery
│   │   ├── protocol.py           # MemoryStore 接口
│   │   ├── session.py            # Session Memory
│   │   ├── episodic.py           # Episodic Memory + SQLite
│   │   ├── semantic.py           # Semantic Memory + SQLite
│   │   ├── decision.py           # Decision Memory + SQLite
│   │   ├── importance.py         # 重要性评分
│   │   ├── decay.py              # 时间衰减
│   │   ├── policy.py             # 合并策略
│   │   ├── consolidation.py      # 合并引擎
│   │   ├── manager.py            # 统一入口
│   │   ├── snapshot.py           # 快照
│   │   ├── audit.py              # 审计
│   │   └── storage/              # 存储实现
│   ├── knowledge/                # 知识系统
│   │   ├── models.py             # KnowledgeItem / Chunk / Query
│   │   ├── protocol.py           # KnowledgeStore 接口
│   │   ├── manager.py            # 统一入口
│   │   ├── ingestion.py          # 摄入管道
│   │   ├── chunking.py           # 6 种分块策略
│   │   ├── retrieval.py          # Hybrid Retrieval
│   │   ├── ranking.py            # 混合排序
│   │   └── ...
│   ├── providers/                # Provider 抽象层
│   │   ├── base.py               # BaseProvider
│   │   ├── registry.py           # ProviderRegistry
│   │   ├── factory.py            # ProviderFactory
│   │   ├── llm/                  # LLM 协议 + Mock
│   │   ├── embedding/            # Embedding 协议 + Mock
│   │   ├── vector/               # Vector 协议 + Mock
│   │   └── storage/              # Storage 协议 + Mock
│   ├── agents/                   # Agent 运行时
│   │   ├── models.py             # AgentInfo / Request / Response
│   │   ├── protocol.py           # AgentRuntime 接口
│   │   ├── runtime.py            # DefaultAgentRuntime
│   │   ├── executor.py           # AgentExecutor
│   │   ├── lifecycle.py          # AgentLifecycleManager
│   │   ├── context.py            # ContextBuilder
│   │   ├── session.py            # AgentSession
│   │   └── registry.py           # AgentRegistry
│   ├── tools/                    # Tool 运行时
│   │   ├── models.py             # ToolInfo / Request / Result
│   │   ├── protocol.py           # ToolProtocol
│   │   ├── registry.py           # ToolRegistry
│   │   ├── executor.py           # ToolExecutor
│   │   ├── sandbox.py            # ToolSandbox
│   │   ├── permissions.py        # PermissionManager
│   │   ├── validator.py          # ToolValidator
│   │   ├── audit.py              # ToolAuditLogger
│   │   ├── metrics.py            # ToolMetricsCollector
│   │   ├── builtin/              # 内置工具（Echo/Calc/DateTime/UUID）
│   │   └── adapters/
│   │       ├── mcp/              # MCP Adapter
│   │       │   ├── models.py     # MCP 数据模型
│   │       │   ├── protocol.py   # MCPClientProtocol
│   │       │   ├── client.py     # MCPClient 实现
│   │       │   ├── wrapper.py    # MCPToolWrapper
│   │       │   ├── converter.py  # 格式转换
│   │       │   ├── registry.py   # MCPToolRegistry
│   │       │   └── mock.py       # Mock MCP Server
│   │       ├── protocol.py       # ToolAdapterProtocol
│   │       └── registry.py       # AdapterRegistry
│   └── workflow/                 # Workflow 引擎
│       ├── models.py             # Workflow 数据模型
│       ├── protocol.py           # WorkflowProtocol
│       ├── runtime.py            # WorkflowRuntime
│       ├── executor.py           # WorkflowExecutor
│       ├── planner.py            # Planner（Rule-based）
│       ├── state.py              # WorkflowStateMachine
│       ├── checkpoint.py         # CheckpointManager
│       ├── registry.py           # WorkflowRegistry
│       ├── events.py             # WorkflowEvents
│       ├── config.py             # WorkflowConfig
│       └── exceptions.py         # 异常定义
├── docs/                         # 文档
│   ├── governance/               # 治理策略（6 文件）
│   ├── rfc/                      # RFC（11 篇）
│   ├── adr/                      # ADR（21 篇）
│   └── project/                  # 项目健康度（9 文件）
├── tests/                        # 测试
│   ├── core/bus/
│   ├── core/database/
│   ├── core/memory/
│   ├── core/knowledge/
│   ├── core/providers/
│   ├── core/agents/
│   ├── core/tools/
│   ├── core/workflow/
│   └── integration/
├── CHANGELOG.md
├── README.md
└── ARCHITECTURE.md
```
