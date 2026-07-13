"""Knowledge Layer configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChunkingConfig:
    """Chunking configuration."""
    strategy: str = "recursive"          # fixed_length | sentence | paragraph | markdown | recursive | token_window
    chunk_size: int = 512                # characters or tokens
    chunk_overlap: int = 50
    token_window_size: int = 256
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", ". ", "。", " ", ""])


@dataclass
class RetrievalConfig:
    """Retrieval configuration."""
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    default_top_k: int = 10
    min_score: float = 0.0
    hybrid_enabled: bool = True


@dataclass
class KnowledgeConfig:
    """Knowledge Layer configuration."""
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    cache_enabled: bool = True
    cache_ttl: int = 300
