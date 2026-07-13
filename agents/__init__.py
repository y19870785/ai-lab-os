"""Agent Layer。

AI-Lab 的智能 Agent 层，承载所有 Agent 的定义、编排和执行。
遵循 RFC-003 定义的 Agent 架构。

架构设计：身份驱动 + 能力组合
- AgentIdentity：Agent 的身份声明
- CapabilityDecl + Tool：Agent 的能力声明
- MemoryProfile：Agent 的记忆关联
- AgentPermission：Agent 的权限边界
- AgentLifecycleManager：Agent 的完整生命周期

使用方式：
    from agents import AgentIdentity, AgentRole
    from agents.tools import ToolRegistry

    # 定义 Agent 身份
    identity = AgentIdentity(
        name="行业分析师",
        role=AgentRole.ANALYST,
        capabilities=[CapabilityDecl(name="data_analysis", type=CapabilityType.SKILL)],
    )

    # 注册到生命周期管理器
    agent_id = await lifecycle.define(identity)
    await lifecycle.initialize(agent_id)
    await lifecycle.activate(agent_id)
"""

__version__ = "0.1.0"
