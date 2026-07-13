"""Knowledge Layer 配置模型。"""

from __future__ import annotations

from pydantic import BaseModel


class KnowledgeLayerConfig(BaseModel):
    """Knowledge Layer 全局配置。"""
    enabled: bool = True
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    default_top_k: int = 10
    enable_hybrid_search: bool = True
