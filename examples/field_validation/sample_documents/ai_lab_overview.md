# AI-Lab 系统架构

AI-Lab 是一个个人级 AI 操作系统，采用分层架构：

## 核心概念

- **Memory Layer**: 四层记忆系统（Session / Episodic / Semantic / Decision）
- **Knowledge Layer**: 知识管理系统（Ingestion → Chunk → Embedding → Retrieval）
- **Provider Layer**: 模型抽象层（LLM / Embedding / Vector / Storage）
- **Agent Runtime**: 智能 Agent 运行时
- **Tool Runtime**: 统一工具执行框架

## API

- REST API: http://localhost:8000
- OpenAPI Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
