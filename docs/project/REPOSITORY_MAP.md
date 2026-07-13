# AI-Lab Repository Map —— 仓库导航索引

> 冻结版本：v0.32.4 | 日期：2026-07-14

---

## 一级目录职责

| 目录 | 职责 | 入口文件 |
|---|---|---|
| `core/` | 框架核心：EventBus、Memory、Knowledge、Provider、Agent、Tool、Workflow、Scheduler、Task、Coordination、Workspace | 各子目录 `__init__.py` |
| `applications/` | 业务应用：CEO Assistant | `applications/runtime.py` |
| `cli/` | 命令行入口 | `cli/main.py` → `python -m cli ceo` |
| `api/` | REST API（FastAPI） | `api/app.py` |
| `scripts/` | 启动/诊断/安装脚本 | `scripts/start.bat` |
| `tests/` | 全量测试 | `pytest tests/` |
| `docs/` | RFC、ADR、架构文档、项目状态 | `docs/project/PROJECT_BRAIN.md` |
| `config/` | YAML 配置 + .env 模板 | `config/default.yaml` |
| `product/` | 产品需求文档 | `product/VISION.md` |
| `prompts/` | Prompt 模板 | — |
| `examples/` | 可运行 Demo | `examples/enterprise_assistant/` |
| `benchmarks/` | 性能基准 | `benchmarks/benchmark_memory.py` |
| `deploy/` | Docker 部署 | `deploy/docker-compose.yml` |
| `data/` | 持久化数据（SQLite + Chroma） | `data/sqlite/`, `data/chroma/` |
| `logs/` | 运行日志 | — |
| `knowledge/` | 知识库独立模块 | `knowledge/manager.py` |
| `agents/` | Agent 角色/工具配置 | `agents/roles/` |
| `workflows/` | Workflow 定义 | — |
| `database/` | 数据库入口（遗留，已迁移到 core/database） | `database/__init__.py` |

---

## 核心模块入口

| 模块 | Manager/Runtime | Protocol | Registry |
|---|---|---|---|
| Memory | `core/memory/manager.py` | `core/memory/protocol.py` | — |
| Knowledge | `core/knowledge/manager.py` | `core/knowledge/protocol.py` | — |
| Provider | `core/providers/factory.py` | `core/providers/llm/protocol.py` | `core/providers/registry.py` |
| Agent | `core/agents/runtime.py` | `core/agents/protocol.py` | `core/agents/registry.py` |
| Tool | `core/tools/executor.py` | `core/tools/protocol.py` | `core/tools/registry.py` |
| MCP | `core/tools/adapters/mcp/client.py` | `core/tools/adapters/mcp/protocol.py` | `core/tools/adapters/mcp/registry.py` |
| Workflow | `core/workflow/runtime.py` | `core/workflow/protocol.py` | `core/workflow/registry.py` |
| Scheduler | `core/scheduler/runtime.py` | `core/scheduler/protocol.py` | `core/scheduler/registry.py` |
| Task | `core/task/runtime.py` | — | — |
| Coordination | `core/coordination/orchestrator.py` | `core/coordination/protocol.py` | `core/coordination/registry.py` |
| Application | `applications/runtime.py` | `applications/models.py` | `applications/registry.py` |
| EventBus | `core/bus/bus.py` | `core/bus/event.py` | — |
| Database | `core/database/manager.py` | — | — |

---

## 配置入口

| 文件 | 用途 |
|---|---|
| `.env` | 环境变量（API Key、模型、数据库路径） |
| `config/default.yaml` | 默认 YAML 配置 |
| `config/alpha.yaml` | Alpha 环境配置 |
| `config/development.yaml` | 开发环境配置 |

---

## 启动入口

| 入口 | 命令 |
|---|---|
| 交互式 CLI | `scripts\start.bat` 或 `python -m cli ceo` |
| API 服务 | `scripts\start_api.bat` 或 `python -m uvicorn api.app:app` |
| 健康检查 | `python -m cli health` |
| 诊断 | `scripts\diagnose.bat` |
| 安装 | `scripts\setup.bat` |

---

## 测试入口

| 入口 | 命令 |
|---|---|
| 全量（不含 Real） | `python -m pytest tests/ -q -m "not real"` |
| Real Provider | `python -m pytest tests/real/ -q -m real` |
| 全量 | `python -m pytest tests/ -q` |
| 单模块 | `python -m pytest tests/core/memory/ -q` |

---

## 文档入口

| 文档 | 路径 |
|---|---|
| 项目大脑 | `docs/project/PROJECT_BRAIN.md` |
| 项目状态 | `docs/project/PROJECT_STATUS.md` |
| 架构文档 | `ARCHITECTURE.md` |
| 产品愿景 | `product/VISION.md` |
| 产品需求 | `product/REQUIREMENTS.md` |
| RFC 索引 | `docs/rfc/` |
| ADR 索引 | `docs/adr/` |
| 技术债 | `docs/project/TECHNICAL_DEBT.md` |
| 路线图 | `docs/project/ROADMAP.md` |
| 已知限制 | `docs/project/KNOWN_LIMITATIONS.md` |

---

## Demo 入口

| Demo | 路径 |
|---|---|
| Enterprise Assistant | `examples/enterprise_assistant/` |
| Daily Assistant | `examples/daily_assistant/` |
| Document QA | `examples/document_qa/` |
| Workflow Demo | `examples/workflow_demo/` |
| Tool Demo | `examples/tool_demo/` |
| Knowledge Demo | `examples/knowledge_demo/` |
| Scheduler Demo | `examples/scheduler_demo/` |
| Alpha Application | `examples/alpha_application/` |
| Field Validation | `examples/field_validation/` |

---

## Docker 入口

| 文件 | 用途 |
|---|---|
| `deploy/Dockerfile` | 容器镜像 |
| `deploy/docker-compose.yml` | 编排配置 |
| `deploy/healthcheck.py` | 健康检查 |
| `deploy/README.md` | 部署说明 |
