# AI-Lab Public API Inventory —— 公共 API 清单

> 冻结版本：v0.32.4 | 日期：2026-07-14

## 核心 Runtime / Manager

| 模块 | 入口文件 | 主要方法 |
|---|---|---|
| MemoryManager | `core/memory/manager.py` | save_memory / retrieve_memory / search_memory / delete_memory / register_store |
| KnowledgeManager | `core/knowledge/manager.py` | ingest / retrieve / search / delete / reindex / statistics |
| ApplicationRuntime | `applications/runtime.py` | initialize / execute / register_application / list_applications |
| AgentRuntime | `core/agents/runtime.py` | run / initialize / shutdown |
| ToolExecutor | `core/tools/executor.py` | execute |
| WorkflowRuntime | `core/workflow/runtime.py` | create / start / pause / resume / cancel |
| SchedulerRuntime | `core/scheduler/runtime.py` | schedule / cancel_job / reschedule_one_shot / list_job_runs / start / shutdown |
| ReminderService / Bridge | `core/reminders/` | create / get / list / reschedule / cancel / reconcile |
| TaskRuntime | `core/task/runtime.py` | create / start / pause / resume / retry |
| AgentOrchestrator | `core/coordination/orchestrator.py` | create_team / coordinate |

## 基础服务

| 模块 | 入口文件 | 主要方法 |
|---|---|---|
| EventBus | `core/bus/bus.py` | publish / subscribe / unsubscribe / start / stop |
| DatabaseManager | `core/database/manager.py` | get_connection / close_all / health_check / vacuum / backup / restore |

## Provider

| 模块 | 入口文件 | 协议 |
|---|---|---|
| LLMProvider | `core/providers/llm/protocol.py` | generate / stream / count_tokens / list_models |
| EmbeddingProvider | `core/providers/embedding/protocol.py` | embed / embed_batch / dimension |
| VectorProvider | `core/providers/vector/protocol.py` | insert / search / delete / update |
| StorageProvider | `core/providers/storage/protocol.py` | save / load / delete / exists / list |

## Provider 实现

| 实现 | 文件 |
|---|---|
| OpenAILLMProvider (DeepSeek) | `core/providers/llm/openai.py` |
| LocalEmbeddingProvider | `core/providers/embedding/local.py` |
| ChromaVectorProvider | `core/providers/vector/chroma.py` |
| Mock Providers | `core/providers/{llm,embedding,vector,storage}/mock.py` |

## 注意事项

1. 业务层只能通过 Manager / Runtime 操作，禁止直接访问 Store 或 Provider
2. MemoryManager 是 Memory Layer 唯一入口
3. ApplicationRuntime.execute() 是 Application Layer 唯一入口
4. 事件只能通过 EventBus 发布，不能直接调用
