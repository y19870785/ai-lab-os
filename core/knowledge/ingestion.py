"""Knowledge Ingestion Pipeline.

Plug-in based pipeline: Reader → Cleaner → Normalizer → Metadata → Chunker → Embedding → Vector Store → Knowledge Store.

Every step is replaceable. No hard-coded logic.
"""

from __future__ import annotations

from typing import Any

from core.knowledge.models import KnowledgeItem, DocumentChunk, SourceType, KnowledgeType
from core.knowledge.chunking import ChunkStrategy, get_chunker
from core.knowledge.metadata import MetadataExtractorRegistry, build_default_registry
from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.vector.protocol import VectorProvider


class IngestionPipeline:
    """Document → Chunks → Embeddings → Vectors → Knowledge Items."""

    def __init__(
        self,
        chunker: ChunkStrategy | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        vector_provider: VectorProvider | None = None,
        metadata_registry: MetadataExtractorRegistry | None = None,
        chunking_config: dict[str, Any] | None = None,
    ) -> None:
        self._chunker = chunker or get_chunker("recursive")
        self._embedding = embedding_provider
        self._vector = vector_provider
        self._metadata = metadata_registry or build_default_registry()

    async def ingest(
        self,
        content: str,
        title: str = "",
        source: str = "",
        source_type: SourceType = SourceType.PLAINTEXT,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        base_metadata: dict[str, Any] | None = None,
        author: str = "",
        language: str = "",
        tags: list[str] | None = None,
        item_id: str | None = None,
    ) -> tuple[KnowledgeItem, list[DocumentChunk]]:
        """Run the full ingestion pipeline.

        Returns:
            (KnowledgeItem, list of DocumentChunks)
        """
        # 1. Clean (basic: strip, normalize whitespace)
        cleaned = self._clean(content)

        # 2. Normalize (basic: consistent line endings)
        normalized = self._normalize(cleaned)

        # 3. Extract metadata
        meta = self._metadata.extract(normalized, base_metadata or {})
        if language:
            meta["language"] = language
        if tags:
            meta["tags"] = list(set(meta.get("tags", []) + tags))

        # 4. Create KnowledgeItem
        from uuid import uuid4
        kid = item_id or uuid4().hex
        item = KnowledgeItem(
            id=kid,
            title=title,
            source=source,
            source_type=source_type,
            knowledge_type=knowledge_type,
            content=normalized[:10000],  # Store first 10k chars as preview
            metadata=meta,
            author=author or meta.get("author", ""),
            language=meta.get("language", "zh"),
            tags=meta.get("tags", []),
            references=meta.get("references", []),
        )

        # 5. Chunk
        chunks = self._chunker.chunk(normalized, kid)

        # 6. Embed + Index into Vector Store
        if self._embedding and self._vector:
            for chunk in chunks:
                vec = await self._embedding.embed_query(chunk.content)
                from core.providers.vector.protocol import VectorRecord
                await self._vector.insert("knowledge", [
                    VectorRecord(
                        id=chunk.chunk_id,
                        vector=vec,
                        metadata={"document_id": kid, "chunk_index": chunk.index},
                    ),
                ])
                chunk.embedding_id = chunk.chunk_id

        return item, chunks

    def _clean(self, text: str) -> str:
        """Basic text cleaning."""
        # Remove excessive whitespace
        import re
        text = re.sub(r'[\t\r]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _normalize(self, text: str) -> str:
        """Normalize text."""
        # Normalize line endings
        return text.replace('\r\n', '\n')

    @property
    def chunker(self) -> ChunkStrategy:
        return self._chunker

    @property
    def metadata_registry(self) -> MetadataExtractorRegistry:
        return self._metadata
