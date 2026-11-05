"""存储层抽象。"""

from knowledge.storage.protocol import GraphStore, KnowledgeStore, VectorStore

__all__ = ["GraphStore", "KnowledgeStore", "VectorStore"]
