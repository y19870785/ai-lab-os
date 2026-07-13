"""Local SentenceTransformer Embedding Provider.

Uses sentence-transformers for offline, local embedding.
"""

from __future__ import annotations

import math
from typing import Any

from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding via sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu") -> None:
        info = ProviderInfo(
            provider_id=f"local-{model_name}",
            provider_type=ProviderType.EMBEDDING,
            name="local",
            version="1.0.0",
            description=f"Local SentenceTransformer Embedding ({model_name})",
            capabilities=[
                ProviderCapability(name="embed", version="1.0"),
                ProviderCapability(name="batch_embed", version="1.0"),
            ],
        )
        super().__init__(info)
        self._model_name = model_name
        self._device = device
        self._model: Any = None

    async def _do_initialize(self) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self._model_name, device=self._device)

    async def _do_shutdown(self) -> None:
        self._model = None

    async def _do_health_check(self) -> bool:
        return self._model is not None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._require_ready()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    async def embed_query(self, query: str) -> list[float]:
        self._require_ready()
        embedding = self._model.encode(query, normalize_embeddings=True)
        return embedding.tolist()

    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension() if self._model else 384

    def model_name(self) -> str:
        return self._model_name

    def normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]
