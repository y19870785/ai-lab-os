"""知识权限模型。"""

from __future__ import annotations

from pydantic import BaseModel

from knowledge.models import AccessLevel


class KnowledgePermission(BaseModel):
    """知识条目权限控制。"""
    knowledge_id: str = ""
    access_level: AccessLevel = AccessLevel.PRIVATE
    owner_id: str = ""
    allowed_users: list[str] = []
    allowed_roles: list[str] = []
    can_read: bool = True
    can_write: bool = False
    can_delete: bool = False
    can_share: bool = False
