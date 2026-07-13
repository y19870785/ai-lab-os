# ADR-005: Agent 身份模型

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 005                                  |
| **标题**     | Agent 身份模型                         |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-003                              |
| **取代**     | —                                    |

## 1. 背景

Agent Layer 需要一个统一的身份模型来回答三个问题：

1. **Who** — Agent 是谁？（身份声明）
2. **What** — Agent 能做什么？（能力声明）
3. **How** — Agent 怎么做？（工具/记忆/权限配置）

在 RFC-001 中，`core/agent/` 已经定义了 `AgentSpec` 作为 Agent 的技术描述（版本、超时等基础设施属性），但缺少语义层的身份定义。

需要设计 Agent 身份模型，使其：
- 区分"Agent 类型"和"Agent 实例"
- 支持预定义角色和自定义角色
- 与能力/工具/权限/记忆系统解耦，但可组合

## 2. 决策

### 2.1 Agent 身份模型的三层结构

```
Agent 身份 = 身份声明 + 能力声明 + 配置绑定
                │            │            │
           AgentIdentity  CapabilityDecl  MemoryProfile
                                          AgentPermission
```

这三层独立设计，但通过 `agent_id` 关联。

### 2.2 关键设计决策

**决策 1：角色（Role）作为"性格模板"，而非"类继承"**

角色不是 Agent 的父类，而是预定义的身份+能力+权限组合模板：
- `ANALYST` 角色 = Analyst 身份 + 数据分析能力 + 数据读取权限 + Session+Episodic 记忆
- 用户创建 Agent 时可以选择角色模板，然后按需调整

**决策 2：Capability 是声明式，而非实现式**

Agent 声明"我会 web_search"，但不提供实现。实现由 ToolRegistry 根据 `tool_name` 匹配。

原因：
- 同一个能力可以用不同后端实现（如 web_search 可以是 Google API 或 Bing API）
- Agent 不需要关心底层实现细节

**决策 3：AgentPermission 独立于 Identity**

权限不是身份的一部分，而是运行时绑定的配置。原因：
- Agent 可以在不同环境（dev/staging/prod）有不同的权限
- 管理员可以临时调整 Agent 权限而不影响身份声明

### 2.3 与 Core AgentSpec 的关系

```
core.agent.AgentSpec           agents.AgentIdentity
─────────────────              ───────────────────
技术层描述                     语义层描述
version / timeout              角色 / 能力 / 画像
实例管理用                      业务编排用
由 AgentRuntime 读取           由 AgentLayer 读取
```

两者通过 `agent_id` 关联。Core Runtime 负责"让 Agent 跑起来"，Agent Layer 负责"让 Agent 知道自己是 谁、该做什么"。

### 2.4 AgentLifecycle 状态机设计

状态机采用显式状态转换，每个转换可以触发钩子（hook）：

```python
TRANSITIONS = {
    DEFINED: [INITIALIZED],
    INITIALIZED: [ACTIVE, ERROR],
    ACTIVE: [RUNNING, PAUSED, DISABLED, ERROR],
    RUNNING: [ACTIVE, ERROR],
    PAUSED: [ACTIVE, ERROR],
    ERROR: [ACTIVE, DISABLED],
    DISABLED: [RETIRED, ACTIVE],
    RETIRED: [],
}
```

不允许的转换会抛出 `InvalidTransitionError`。

## 3. 后果

### 正面

- 身份/能力/权限分层清晰，可以独立演进
- 角色模板化降低 Agent 创建成本（选角色 → 微调 → 上线）
- 与 Core AgentSpec 职责分离，不重复

### 负面

- 角色模板的定义缺乏自动化工具（Phase 1 需要手动配置）
- 双层权限模型增加理解和调试复杂度

### 风险

- Capability 声明和 Tool 实现可能不同步（Agent 声明会 web_search，但 ToolRegistry 里没有注册）
  - **缓解**：Agent 初始化时验证 Capability-Tool 绑定
- Lifecycle 状态机过渡图对新手有学习成本
  - **缓解**：提供 `AgentLifecycleManager` 封装所有合法转换

## 4. 理由

三阶段设计演进路径：

```
Phase 1 (当前): 身份模型 + 角色模板 → 定义清楚 Agent 是什么
Phase 2: 动态能力发现 → Agent 启动时自动检测可用 Tool
Phase 3: 运行时能力学习 → Agent 在运行中习得新能力
```

先做好 Phase 1，"定义清楚 Agent 是什么"，不跳过基础直接谈动态发现。

## 5. 相关链接

- [RFC-003 §3.1-3.3](docs/rfc/003-agent-architecture.md#31-整体思路)
- [core/agent/models.py](core/agent/models.py) — AgentSpec / AgentInstance
- [RFC-001 §3.3 模块 5](docs/rfc/001-core-layer-architecture.md#模块-5agent-runtime新增)
