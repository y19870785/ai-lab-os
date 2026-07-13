"""OpenAI Embedding Provider.

遵循 EmbeddingProvider Protocol，接入 OpenAI Embedding API。
"""

from __future__ import annotations

import os
import math
import asyncio
from typing import Any

from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding backend."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "text-embedding-3-small",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self._timeout = timeout
        self._client = None
        self._dim = 1536  # default for text-embedding-3-small
        self._request_count = 0

        info = ProviderInfo(
            provider_id=f"openai-embed-{self._model}",
            provider_type=ProviderType.EMBEDDING,
            name="openai",
            version="2.14.0",
            description=f"OpenAI Embedding Provider ({self._model})",
            capabilities=[
                ProviderCapability(name="embed", version="1.0"),
                ProviderCapability(name="normalize", version="1.0"),
            ],
        )
        super().__init__(info)
        self._info = info

    async def _do_initialize(self) -> None:
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                max_retries=2,
            )
        except ImportError:
            raise RuntimeError("openai package not installed")

        # Determine dimension
        dim_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        self._dim = dim_map.get(self._model, 1536)

    async def _do_shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None

    async def _do_health_check(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.embeddings.create(
                model=self._model, input=["ping"],
            )
            return True
        except Exception:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._require_ready()
        if not texts:
            return []

        t0 = __import__("time").time()
        for attempt in range(3):
            try:
                resp = await asyncio.wait_for(
                    self._client.embeddings.create(
                        model=self._model, input=texts,
                    ),
                    timeout=self._timeout,
                )
                break
            except asyncio.TimeoutError:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        self._request_count += 1
        # Sort by index to preserve order
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed([query])
        return vectors[0] if vectors else []

    def dimension(self) -> int:
        return self._dim

    def model_name(self) -> str:
        return self._model

    def normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    @property
    def metrics(self) -> dict[str, Any]:
        return {
            "request_count": self._request_count,
            "model": self._model,
            "dimension": self._dim,
        }
