"""角色模板。预定义 Agent 角色的身份+能力+权限+记忆默认配置。

角色是"性格模板"——新建 Agent 时选择一个角色，然后按需调整。
"""

from agents.roles.registry import RoleRegistry, RoleTemplate

__all__ = [
    "RoleRegistry",
    "RoleTemplate",
]
