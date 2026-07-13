# AI-Lab Project Context

> AI-Lab 的长期状态文件。任何新的 AI Agent 或开发者读取此文件后，应能快速理解项目全貌。

---

## 项目使命

**构建个人级的 AI 操作系统（Personal AI Operating System）。**

AI-Lab 不只是一个项目，而是一个平台：让个人可以拥有、控制和扩展自己的 AI 能力。所有 AI 应用均基于 AI-Lab 构建，而非各自为战。

## 项目愿景

- **五年内**：AI-Lab 成为个人用户的默认 AI 基础设施——像操作系统一样管理 AI 能力、数据和决策。
- **用户掌控**：用户拥有全部数据、模型选择和决策权。AI 辅助决策，不替代人的最终判断。
- **可扩展**：从单 Agent 到多 Agent 协作，从本地模型到云端模型，从个人使用到团队协作——架构支持平滑演进。

## 核心设计原则

1. **模块化** — 每层独立，可替换。下层不依赖上层。
2. **文档先行** — 重大变更先写 RFC，架构决策记录 ADR，治理规则公开透明。
3. **配置驱动** — 避免硬编码，环境分离，运行时热加载。
4. **可观测性** — 日志 / 指标 / 链路追踪贯穿所有层。
5. **实用主义** — Phase 1 追求"可工作"胜过"可扩展"；Phase 2+ 在可工作基础上演进。

## 当前架构版本

**v0.6.0**（详见 [VERSIONING_POLICY.md](VERSIONING_POLICY.md)）

## 当前开发阶段

**Foundation Phase（基础建设阶段）**

所有五层架构设计 + Governance 治理体系已完成，处于基础建设收尾阶段。

- Phase 1.1：Core Layer 架构 → ✅ 完成（RFC-001, ADR-001, ADR-002）
- Phase 1.2：Memory Layer 架构 → ✅ 完成（RFC-002, ADR-003, ADR-004）
- Phase 1.3：Agent Layer 架构 → ✅ 完成（RFC-003, ADR-005）
- Phase 1.4：Knowledge Layer 架构 → ✅ 完成（RFC-004, ADR-006）
- Phase 1.5：Governance Layer → ✅ 完成（PROJECT_CONTEXT, DEVELOPMENT_POLICY, AGENT_POLICY, KNOWLEDGE_POLICY, MODEL_POLICY, VERSIONING_POLICY）

## 已完成模块

### 文档体系

| 类别 | 文件 | 说明 |
| --- | --- | --- |
| 架构总览 | [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) | 五层架构完整描述 |
| RFC | [RFC-001](../rfc/001-core-layer-architecture.md) 至 RFC-004 | 各层架构设计 |
| ADR | ADR-001 至 ADR-006 | 关键架构决策记录 |
| 开发指南 | [DEVELOPMENT_GUIDE.md](../guides/DEVELOPMENT_GUIDE.md) | 开发流程和规范 |
| 治理 | docs/governance/ 下 6 个文件 | 长期运行治理体系 |

### 代码骨架

| 包 | 说明 |
| --- | --- |
| `core/` | 基础设施层：配置、日志、消息总线、数据访问、Agent 运行时、身份管理、记忆系统 |
| `agents/` | Agent 层：身份模型、工具系统、角色模板、生命周期管理、Agent 间通信协议 |
| `knowledge/` | 知识层：五种知识类型数据模型、切割策略、Embedding 接口、检索引擎骨架 |
| `applications/` | 应用层占位（待 Phase 2 实现） |

## 当前任务

建立 AI-Lab 长期运行所需的治理体系，包括：
- 项目上下文总览（本文档）
- 开发规范和策略
- Agent 管理规范
- 知识管理规范
- 模型管理规范
- 版本管理规范

## 未来路线

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Foundation | 五层架构设计 + 治理体系 | ✅ 完成 |
| Phase 2.1 | Core Layer 实现（配置/日志/消息总线） | 📋 未开始 |
| Phase 2.2 | Memory Layer 实现 | 📋 未开始 |
| Phase 2.3 | Knowledge Layer 实现 | 📋 未开始 |
| Phase 2.4 | Agent Layer 实现 | 📋 未开始 |
| Phase 3 | Application Layer（投资助手等） | 📋 未开始 |
| Phase 4 | 多 Agent 协作 + 高级记忆 + 知识图谱 | 🔮 规划中 |

## 技术栈

- **语言**：Python 3.11+
- **配置**：Pydantic + YAML + 环境变量
- **序列化**：JSON（结构化日志）、Pickle（向量缓存）
- **数据**：SQLite（关系存储）、Chroma（向量存储）、文件系统（原始文件）
- **通信**：asyncio（进程内消息总线）
- **测试**：pytest + pytest-asyncio

---

> 最后更新：2026-07-12 | 维护者：Lin Yuyan
