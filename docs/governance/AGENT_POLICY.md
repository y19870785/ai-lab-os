# AI-Lab Agent Policy

> Agent 管理规范。定义 Agent 的创建、命名、权限、生命周期和禁止行为。

---

## 1. Agent 创建流程

所有 Agent 的开发遵循以下标准化流程：

```
需求提出
    │
    ▼
[1] 需求评审
    │  - 明确 Agent 职责边界
    │  - 确认是否与已有 Agent 职责重叠
    │  - 确认所需能力（工具 / 技能 / 知识域）
    ▼
[2] 角色定义
    │  - 选择预定义角色模板或创建 CUSTOM 角色
    │  - 定义 AgentIdentity（name / description / capabilities）
    │  - 记录到 RFC（重大 Agent）或直接配置（简单 Agent）
    ▼
[3] 权限设计
    │  - 定义 Agent 级权限（allowed_tools / blocked_tools）
    │  - 定义用户级约束（需审批的操作 / token 上限）
    │  - 确认数据访问范围（memory_types / knowledge 级别）
    ▼
[4] 工具绑定
    │  - 注册所需 Tool（或确认已有 Tool 可用）
    │  - 配置 Tool 参数（timeout / requires_approval）
    │  - 开发新 Tool 需先定义接口（遵循 Tool 协议）
    ▼
[5] Memory 配置
    │  - 定义 MemoryProfile（启用类型 / 检索策略 / 写入策略）
    │  - 配置初始化加载的记忆模板（如有）
    ▼
[6] 测试
    │  - 单元测试：Agent 生命周期状态转换
    │  - 集成测试：Agent → Tool → Memory 完整链路
    │  - 安全测试：越权操作拦截验证
    ▼
[7] 上线
    │  - 更新 Agent 注册表
    │  - 更新相关文档（Agent 目录 / 用户指南）
    │  - 监控运行状态（初始阶段重点关注）
    ▼
完成
```

## 2. Agent 命名规范

| 规则 | 要求 | 示例 |
| --- | --- | --- |
| agent_id | 小写 + 下划线 | `industry_analyst`, `schedule_secretary` |
| 显示名称 | 中文，2-6 字 | `行业分析师`, `日程秘书` |
| Role 取值 | 必须为 AgentRole 枚举值 | `analyst`, `secretary`, `custom` |
| version | 遵循 Semantic Versioning | `1.0.0` |

命名原则：
- 名称应反映 Agent 的核心职责，而非实现方式
- 避免"通用"名称（如 `my_agent`），必须有明确的职责描述
- 同一角色类型使用统一的命名模式（如 `industry_analyst`、`financial_analyst`）

## 3. Agent 权限原则

### 最小权限原则

Agent 只应获得完成其职责所需的最小权限集。

```
好的：analyst Agent 有 knowledge_query + code_execute 权限
不好的：analyst Agent 有 system_config 权限

好的：秘书 Agent 有 memory_write(SESSION) 权限
不好的：秘书 Agent 有 memory_write(EPISODIC) 权限
```

### 双层权限检查

```
Agent 请求执行操作
    │
    ▼
[Layer 1] Agent 自身权限检查
    │  这个 Agent 允许调用这个 Tool 吗？
    │  这个 Agent 可以访问这个 MemoryType 吗？
    │
    ▼
[Layer 2] 用户级委托权限检查
    │  当前用户授权这个 Agent 执行此操作吗？
    │  这个操作需要用户确认吗？（requires_approval）
    │
    ▼
通过 → 执行 | 不通过 → 拒绝 + 审计日志
```

### 需要用户审批的操作

- 写入/删除文件
- 调用外部 API（已配置白名单的除外）
- 修改系统配置
- 执行代码（sandbox 模式以外）
- 删除已有知识/记忆

## 4. Agent 生命周期管理

见 [RFC-003](../rfc/003-agent-architecture.md) 定义的生命周期状态机。

| 状态 | 含义 | 管理操作 |
| --- | --- | --- |
| DEFINED | 身份已注册 | 可修改身份定义 |
| INITIALIZED | 能力/记忆/权限已绑定 | 可修改绑定关系 |
| ACTIVE | 可接收任务 | 正常使用 |
| RUNNING | 正在执行任务 | 可强制终止 |
| PAUSED | 暂停 | 不可接收新任务，已有任务继续 |
| ERROR | 异常状态 | 需人工排查 |
| DISABLED | 管理员禁用 | 不可用，保留配置 |
| RETIRED | 已退役 | 保留记录，不可恢复 |

### 自动退役规则

- Agent 连续 90 天未被使用 → 标记为待退役
- Agent 版本连续 3 个大版本未更新 → 标记为待退役
- 退役前通知 owner，7 天内无响应则自动退役

## 5. Agent 间协作规则

| 规则 | 说明 |
| --- | --- |
| 委托 | Orchestrator Agent 可以委托子任务给 Specialist Agent |
| 查询 | Agent 可以向另一个 Agent 发送信息查询 |
| 通知 | Agent 可以单向通知其他 Agent |
| 广播 | 仅 Orcherstrator 和 System Agent 有权广播 |

**禁止行为：**
- Agent 不可委托任务给自己
- Agent 不可修改其他 Agent 的身份定义
- Agent 不可直接调用另一 Agent 的内部方法（必须通过 Agent Protocol）

## 6. Agent 禁止行为清单

| 禁止行为 | 说明 | 后果 |
| --- | --- | --- |
| 越权操作 | 调用未授权的 Tool 或访问未授权的 Memory | 自动 Disabled |
| 循环委托 | A → B → C → A 的委托循环 | 检测后自动终止 |
| 自我修改 | 修改自己的身份定义或权限 | 审计警报 + Disabled |
| 资源滥用 | 单次运行超过 max_tokens 或 max_tool_calls | 强制终止 |
| 跨层调用 | 跳过 Agent Protocol 直接访问 Core Layer 内部 | 架构违规，需 Review |

---

> 最后更新：2026-07-12 | 维护者：Lin Yuyan
