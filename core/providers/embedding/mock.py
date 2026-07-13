"""Mock Embedding Provider."""

from __future__ import annotations

import math
import hashlib

from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding that generates deterministic pseudo-vectors.

    Uses SHA-256 hash to produce consistent vectors for the same text.
    DIMENSION is fixed at 384 (matching common small models).
    """

    DIMENSION = 384

    def __init__(self) -> None:
        info = ProviderInfo(
            provider_id="mock-emb-001",
            provider_type=ProviderType.EMBEDDING,
            name="mock",
            version="1.0.0",
            description="Mock embedding provider",
            capabilities=[
                ProviderCapability(name="embed", version="1.0"),
            ],
        )
        super().__init__(info)

    async def _do_initialize(self) -> None:
        pass

    async def _do_shutdown(self) -> None:
        pass

    async def _do_health_check(self) -> bool:
        return True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._require_ready()
        return [self._text_to_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        self._require_ready()
        return self._text_to_vector(f"query:{query}")

    def dimension(self) -> int:
        return self.DIMENSION

    def model_name(self) -> str:
        return "mock-embed-v1"

    def normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    def _text_to_vector(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-vector from text hash."""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(0, min(len(h), self.DIMENSION)):
            # Normalize byte to [-1, 1]
            vec.append((h[i] / 127.5) - 1.0)
        # Pad with zeros if needed
        while len(vec) < self.DIMENSION:
            vec.append(0.0)
        return vec
