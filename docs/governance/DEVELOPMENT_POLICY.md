# AI-Lab Development Policy

> 开发规范。重大设计先文档，代码实现后同步更新。

---

## 1. 文档优先原则

所有功能开发遵循以下流程：

```
需求分析
    │
    ▼
┌─ 是否重大变更？ ──→ 是 ──→ 写 RFC → 评审 → 定案
│                        ↓
否                        ↓
│                    ┌─ 是否有架构影响？ ──→ 是 ──→ 记录 ADR
│                    │                           ↓
│                    └── 更新架构文档              ↓
│                                               ↓
└────────────────────────────────────────────
    │
    ▼
实现代码 → 测试 → 更新 CHANGELOG → 完成
```

**重大变更**的定义：
- 新增或合并架构层
- 引入新的外部依赖或存储后端
- 修改层间接口协议
- 重构核心数据模型
- 修改文件系统或数据库 Schema

## 2. RFC 使用规则

| 属性 | 规则 |
| --- | --- |
| 编号 | 递增三位数：RFC-001, RFC-002, ... |
| 文件名 | `{编号}-{短横线标题}.md` |
| 存放位置 | `docs/rfc/` |
| 状态流转 | 草稿 → 评审中 → 已定案 → 已实现 |
| 关联 | 必须关联涉及的 ADR 编号 |
| 更新 | 实施完成后更新状态，可关闭或标记为已实现 |

**RFC 模板**：[docs/rfc/000-template.md](../rfc/000-template.md)

## 3. ADR 使用规则

| 属性 | 规则 |
| --- | --- |
| 编号 | 递增三位数：ADR-001, ADR-002, ... |
| 文件名 | `ADR-{编号}-{短横线标题}.md` |
| 存放位置 | `docs/adr/` |
| 状态 | 提议 → 已接受 → 已废弃 → 已取代 |
| 关联 | 必须关联来源 RFC |

**ADR 模板**：[docs/adr/000-template.md](../adr/000-template.md)

## 4. 代码提交规范

### Commit Message 格式

```
<type>(<scope>): <subject>

<body>
```

**Type**：
- `feat` — 新功能
- `fix` — 修复
- `docs` — 文档变更
- `refactor` — 重构（不新增功能也不修 bug）
- `test` — 测试相关
- `chore` — 构建/工具/依赖变更
- `gov` — 治理文档变更（本项目特有）

**Scope**：
- `core` — Core Layer
- `memory` — Memory Layer
- `knowledge` — Knowledge Layer
- `agents` — Agent Layer
- `app` — Application Layer
- `gov` — Governance Layer
- `docs` — 通用文档
- `config` — 配置管理

**示例**：
```
feat(core): 实现 Message Bus 的内存通道

引入 MemoryMessageBus 支持进程内 Event Pub-Sub 和 Task Queue。
基于 asyncio.Queue 实现，无外部依赖。
```

### 分支策略

```
main         ← 稳定版本，只接受 PR
dev          ← 开发分支
feature/*    ← 功能分支（从 dev 拉取）
fix/*        ← 修复分支（从 dev 拉取）
gov/*        ← 治理文档分支（本项目特有）
```

## 5. 质量要求

### 测试

| 层级 | 覆盖率目标 | 工具 |
| --- | --- | --- |
| 单元测试 | ≥ 80% 核心模块 | pytest |
| 集成测试 | 覆盖主要链路 | pytest-asyncio |
| 架构测试 | 验证层间依赖规则 | 自定义 checker |

### 代码审查

- 所有 PR 需要至少一个其他贡献者 review
- Review 关注点：
  1. 是否遵循了层间依赖规则
  2. 是否更新了相关文档（RFC/ADR/ARCHITECTURE）
  3. 类型注解是否完整
  4. 是否有对应测试

## 6. 配置管理规范

- 默认配置写 `config/default.yaml`
- 敏感信息走环境变量（`.env`）
- 运行时覆盖通过 Config API，不直接改 YAML 文件
- 配置变更必须先更新 RFC/ADR，再更新代码

## 7. 其他约定

- **Python 3.11+**，强制类型注解
- **Google 风格 docstring**（函数/类需要）
- **遵循 PEP 8**，使用 ruff 做 lint
- **禁止循环导入** — 每条 import 路径必须是无环 DAG（有 CI 检查）

---

> 最后更新：2026-07-12 | 维护者：Lin Yuyan
