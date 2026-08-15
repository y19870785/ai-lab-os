"""Knowledge Manager——Knowledge Layer 统一入口。"""
# 骨架文件

from knowledge.models import KnowledgeType


class KnowledgeManager:
    """Knowledge Layer 的统一入口。封装所有知识类型的 CRUD 和检索。"""

    async def search(self, query: str, knowledge_types: list[KnowledgeType] | None = None) -> list:
        """执行跨类型知识检索。"""
        return []
