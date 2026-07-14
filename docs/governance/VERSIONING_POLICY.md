# AI-Lab Versioning Policy

> 版本管理规范。定义架构、数据、Agent 和 Prompt 的版本管理规则。

---

## 1. 版本号规则

AI-Lab OS 使用 **Semantic Versioning**，正式版本格式为 `vMAJOR.MINOR.PATCH`：

```
v1.2.3
│ │ │
│ │ └── Patch：Bug 修复、文档更新、配置调整（向下兼容）
│ └──── Minor：功能新增、架构层扩展（向下兼容）
└────── Major：架构重构、API 破坏性变更（不兼容）
```

### 何时增加版本号

| 变更类型 | 示例 | 版本号变更 |
| --- | --- | --- |
| Patch | Bug、并发、错误语义、安全或小范围兼容修复 | Patch +1 |
| Patch | 调整配置默认值 | Patch +1 |
| Minor | 形成新的系统能力或真实业务闭环基线 | Minor +1, Patch 归零 |
| Major | 重写 Core Layer 接口协议 | Major +1, Minor/Patch 归零 |
| Major | 变更存储 Schema | Major +1, Minor/Patch 归零 |
| Major | 删除或重命名已有 API | Major +1, Minor/Patch 归零 |

纯文档对账通常不单独提升产品版本，除非它属于正式 Release PR。当前处于 `0.x` 开发期；Reminder/Scheduler 闭环、Knowledge 进入真实主链路、自动 Tool Calling 或新的真实业务闭环属于 Minor 基线，兼容性稳定化属于 Patch。

### 当前目标基线

**v0.33.0** — 汇总 SP-001 至 SP-003 的 Composition Root、失败语义与 DatabaseManager 连接所有权稳定化成果。

### SP 工作包

- SP 编号是工程工作包，不是产品版本，一个 SP 不要求对应一个版本。
- `SP-003` 表示 DatabaseManager Connection Ownership；`v0.33.0` 表示包含多个稳定化工作包的产品基线。
- `SP-003A`、`SP-003B` 的后缀表示工作包关系，不是 SemVer 预发布后缀。

## 2. 架构升级规则

### 架构变更流程

```
[提议] 写 RFC 描述新架构
    │
    ▼
[评审] 社区/维护者评审（至少 3 天）
    │
    ▼
[记录] 写 ADR 记录决策
    │
    ▼
[实现] 按 RFC 实施
    │
    ▼
[迁移] 制定并执行数据/配置迁移计划（如有）
    │
    ▼
[发布] 更新版本号 + CHANGELOG + ARCHITECTURE.md
    │
    ▼
完成
```

### 架构变更类型

| 类型 | 说明 | 版本 |
| --- | --- | --- |
| 新增层 | 在现有层之间插入新架构层（如 Governance Layer） | Minor |
| 合并层 | 将两个层合并为一个 | Major |
| 拆分层 | 将一个层拆为两个 | Major |
| 重定义层间接口 | 修改层间通信协议 | Major |
| 移除层 | 废弃某层的存在 | Major |

### 向后兼容承诺

- 同一 Major 版本内，所有 Minor 升级必须向后兼容
- 弃用的 API 和接口至少保留一个 Minor 版本后再移除
- 数据格式变更需提供迁移脚本

## 3. 数据迁移规则

### 触发条件

需要执行数据迁移的场景：
- 数据库 Schema 变更（增删改表/字段）
- 向量 Collection 结构变更
- 文件系统目录结构调整
- 数据序列化格式变更（如 JSON → protobuf）

### 迁移流程

```
[1] 评估影响范围
    │  确定需要迁移的数据量、关联模块、回滚方案
    ▼
[2] 编写迁移脚本
    │  scripts/migrations/{version}_{description}.py
    ▼
[3] 测试迁移
    │  在 staging 环境运行，验证数据完整性
    ▼
[4] 执行迁移
    │  备份 → 执行 → 验证
    ▼
[5] 记录迁移
    │  迁移完成后更新 CHANGELOG 和 ADR
```

### 迁移脚本规范

- 迁移脚本放在 `scripts/migrations/` 目录
- 命名格式：`{version}_{short_description}.py`，如 `v0.6.0_add_knowledge_schema.py`
- 每个迁移脚本必须提供 `upgrade()` 和 `downgrade()` 两个函数
- 迁移脚本必须是幂等的（可重复执行而不产生副作用）

## 4. Agent 版本管理

### Agent 版本号

每个 Agent 独立维护版本号，独立于系统版本：

```
agent_spec.version = "1.2.3"
```

### 版本变更触发

| 变更 | 版本 |
| --- | --- |
| 修复 Agent 逻辑错误 | Patch +1 |
| 新增/修改 Agent 的工具绑定 | Minor +1 |
| 修改 Agent 的角色定义 | Minor +1 |
| 修改 Agent 的权限配置 | Minor +1 |
| Agent 重构或能力变更 | Major +1 |

### Agent 版本兼容

- Agent Layer 保证同一 Major 版本内的 Agent 可以共存
- 不同 Major 版本的 Agent 不能同时注册（需迁移）

## 5. Prompt 版本管理

### Prompt 定义

Prompt 是 AI-Lab 的一等公民，与代码分离管理：

```
prompts/
├── __init__.py
├── registry.py              # Prompt 注册中心
├── system/                  # 系统级 Prompt（Agent 身份、工具描述）
│   ├── analyst_v1.txt
│   └── analyst_v2.txt
├── templates/               # Prompt 模板（可变量插值）
│   ├── knowledge_search.j2
│   └── decision_review.j2
└── config.yaml              # Prompt 版本映射配置
```

### Prompt 版本规则

| 规则 | 说明 |
| --- | --- |
| 文件版本 | Prompt 文件名后缀 `_v{数字}`，如 `analyst_v1.txt` |
| 默认版本 | `config.yaml` 中指定当前使用的 Prompt 版本 |
| 回滚 | 保留历史版本文件，回滚只需修改 config.yaml |
| 测试 | Prompt 变更需要记录效果对比（A/B 测试或人工评估） |

### Prompt 与 Agent 的绑定

```yaml
# prompts/config.yaml
prompts:
  agent_defaults:
    analyst:
      system_prompt: "analyst_v2"
      temperature: 0.3
    secretary:
      system_prompt: "secretary_v1"
      temperature: 0.5
  templates:
    knowledge_search: "knowledge_search_v3"
    decision_review: "decision_review_v1"
```

## 6. 产品版本来源

`pyproject.toml` 的 `[project].version` 是 AI-Lab OS 唯一运行时产品版本来源。

- 已安装或 editable install 环境通过 `importlib.metadata.version("ai-lab")` 读取发行包元数据。
- Source checkout 尚无发行包元数据时，`core.__version__` 从仓库 `pyproject.toml` 派生。
- Source fallback 按 `core` 模块位置定位文件，不依赖当前工作目录。
- metadata 与 source metadata 均不可用时必须明确失败，不返回伪造的正式版本。
- Agent、Provider、Application 等组件可以维护独立组件版本，但不得替代产品版本。

| 位置 | 文件 | 说明 |
| --- | --- | --- |
| 唯一真源 | `pyproject.toml` | `[project].version` 产品版本 |
| 运行时入口 | `core/__init__.py` | 从 package metadata 或唯一真源派生 `__version__` |
| 架构文档 | `docs/architecture/ARCHITECTURE.md` | 架构版本标注 |
| 上下文 | `docs/governance/PROJECT_CONTEXT.md` | 项目状态版本 |
| 变更日志 | `CHANGELOG.md` | 按版本记录的变更历史 |
| Git Tag | `vMAJOR.MINOR.PATCH` | 只在 Release PR 审查、合并后基于 main commit 创建 |

### 版本发布清单

每次版本发布前检查：
- [ ] CHANGELOG.md 已更新
- [ ] pyproject.toml 版本号已更新
- [ ] `core.__version__` 与 distribution metadata 一致
- [ ] 版本一致性测试通过
- [ ] 所有新增/修改的文档已提交
- [ ] 所有迁移脚本已验证
- [ ] Release PR 已审查并合并后再创建 Git Tag

---

> 最后更新：2026-07-15 | 维护者：Lin Yuyan
