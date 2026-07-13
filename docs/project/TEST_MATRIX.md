# AI-Lab Test Matrix —— 测试矩阵

> 冻结版本：v0.32.4 | 日期：2026-07-14
> 测试文件总数：104

## 按模块分类

### Core 层

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/core/bus/` | EventBus 发布/订阅/队列 | Mock | ✅ |
| `tests/core/database/` | DatabaseManager 连接池 | Mock | ✅ |
| `tests/core/memory/` | Session/Episodic/Semantic/Decision | Mock | ✅ |
| `tests/core/memory/test_consolidation.py` | 记忆清理/压缩/晋升 | Mock | ✅ |
| `tests/core/memory/test_snapshot.py` | Memory 快照 | Mock | ✅ |
| `tests/core/memory/test_audit.py` | Memory 审计 | Mock | ✅ |
| `tests/core/memory/test_integration.py` | Memory 集成 | Mock | ✅ |
| `tests/core/providers/` | Provider Registry/Factory/Mock | Mock | ✅ |
| `tests/core/knowledge/` | Chunking/Pipeline/Retrieval/Ranking | Mock | ✅ |
| `tests/core/agents/` | Agent Runtime/Registry/Lifecycle | Mock | ✅ |
| `tests/core/tools/` | Tool Runtime/Registry/Sandbox/Permissions | Mock | ✅ |
| `tests/core/workflow/` | Workflow Engine/State Machine/Checkpoint | Mock | ✅ |
| `tests/core/scheduler/` | Scheduler/Trigger/Persistence | Mock | ✅ |
| `tests/core/task/` | Task Runtime/Dependency | Mock | ✅ |
| `tests/core/coordination/` | Multi-Agent Orchestrator | Mock | ✅ |

### Integration

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/integration/test_agent_tool_flow.py` | Agent + Tool 集成 | Mock | ✅ |
| `tests/integration/test_agent_memory_flow.py` | Agent + Memory 集成 | Mock | ✅ |
| `tests/integration/test_agent_knowledge_flow.py` | Agent + Knowledge 集成 | Mock | ✅ |
| `tests/integration/test_agent_provider_flow.py` | Agent + Provider 集成 | Mock | ✅ |
| `tests/integration/test_agent_mcp_flow.py` | Agent + MCP 集成 | Mock | ✅ |
| `tests/integration/test_end_to_end.py` | 端到端 | Mock | ✅ |
| `tests/integration/test_first_interaction.py` | CLI 首次交互 | Mock | ✅ |
| `tests/integration/test_alpha_application.py` | Alpha 应用 | Mock | ✅ |
| `tests/integration/test_knowledge_pipeline.py` | Knowledge Pipeline | Mock | ✅ |
| `tests/integration/test_mcp_client.py` | MCP Client | Mock | ✅ |

### CEO Assistant

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/applications/ceo_assistant/test_daily_brief.py` | Daily Brief | Mock | ✅ |
| `tests/applications/ceo_assistant/test_work_log.py` | Work Log | Mock | ✅ |
| `tests/applications/ceo_assistant/test_task.py` | Task | Mock | ✅ |
| `tests/applications/ceo_assistant/test_decision.py` | Decision | Mock | ✅ |
| `tests/applications/ceo_assistant/test_knowledge_qa.py` | Knowledge QA | Mock | ✅ |

### CLI

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/cli/test_ceo_interactive.py` | CLI Intent Router + 命令 | Mock | ✅ |
| `tests/api/test_api_models.py` | API Models + CLI 导入 | Mock | ✅ |

### 可靠性

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/recovery/` | 系统恢复 | Mock | ✅ |
| `tests/fault_injection/` | 故障注入 | Mock | ✅ |
| `tests/stress/` | 压力测试 | Mock | ✅ |
| `tests/deployment/` | 部署验证 | Mock | ✅ |
| `tests/field/` | 现场验证 | Mock | ✅ |

### Real Provider

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/real/test_ceo_assistant_deepseek.py` | DeepSeek 真实 API | Real | 5 errors（机器代理兼容） |
| `tests/real/test_deepseek_integration.py` | DeepSeek 集成 | Real | — |
| `tests/real/test_knowledge_pipeline_real.py` | Knowledge 真实验证 | Real | — |

### Applications

| 文件 | 测试目标 | Mock/Real | 状态 |
|---|---|---|---|
| `tests/applications/test_runtime.py` | ApplicationRuntime | Mock | ✅ |

---

## 汇总

| 类别 | 文件数 | 测试数 | 状态 |
|---|---|---|---|
| Core Unit | ~60 | ~400 | ✅ |
| Integration | ~10 | ~80 | ✅ |
| CEO Assistant | ~5 | ~25 | ✅ |
| CLI + API | ~3 | ~15 | ✅ |
| 可靠性 (Recovery/Fault/Stress) | ~15 | ~50 | ✅ |
| Real Provider | ~3 | 5 | 5 errors |
| 其他 | ~8 | ~20 | ✅ |
| **总计** | **104** | **712 passed** | **0 failed** |

## 已知缺口

1. Real Provider 测试依赖清除 SOCKS 代理才能运行
2. 无端到端真实验收测试（含真实 LLM + Tool 调用）
3. 无 Docker 部署的集成测试
4. 无 Long-running 稳定性测试
5. 无 API 并发压力测试
