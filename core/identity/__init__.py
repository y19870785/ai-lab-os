"""身份认证与会话管理。

使用方式：
    from core.identity import IdentityManager, User, Session, Credentials

    session = await identity.authenticate(credentials)
    if session:
        await identity.authorize(session.user_id, "agent.run", "agent:analyst")
"""

from core.identity.protocol import IdentityManager
from core.identity.models import User, Session, Credentials, Role, Permission

__all__ = [
    "IdentityManager",
    "User",
    "Session",
    "Credentials",
    "Role",
    "Permission",
]
