"""身份管理器抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.identity.models import Credentials, Permission, Session, User


class IdentityManager(ABC):
    """身份认证与会话管理。"""

    @abstractmethod
    async def authenticate(self, credentials: Credentials) -> Session | None:
        """认证用户凭据，返回有效会话。"""
        ...

    @abstractmethod
    async def authorize(self, user_id: str, action: str, resource: str) -> bool:
        """检查用户是否有权限执行指定操作。"""
        ...

    @abstractmethod
    async def create_session(self, user_id: str) -> Session:
        """为用户创建新会话。"""
        ...

    @abstractmethod
    async def validate_session(self, token: str) -> Session | None:
        """验证会话 token 是否有效。"""
        ...

    @abstractmethod
    async def revoke_session(self, token: str) -> None:
        """撤销指定会话。"""
        ...

    @abstractmethod
    async def get_user(self, user_id: str) -> User | None:
        """获取用户信息。"""
        ...
