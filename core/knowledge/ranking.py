"""Knowledge ranking — composite scoring for retrieval results.

Supports:
- Vector score (from similarity search)
- Keyword score (TF-IDF)
- Freshness boost (newer = higher)
- Importance boost
- Confidence boost

Designed for future extension: LLM reranker, cross-encoder.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from core.knowledge.models import KnowledgeItem, KnowledgeResult


class RankingConfig:
    """Ranking weight configuration."""

    def __init__(
        self,
        vector_weight: float = 0.4,
        keyword_weight: float = 0.2,
        freshness_weight: float = 0.15,
        importance_weight: float = 0.15,
        confidence_weight: float = 0.1,
        freshness_half_life_days: float = 90.0,
    ) -> None:
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.freshness_weight = freshness_weight
        self.importance_weight = importance_weight
        self.confidence_weight = confidence_weight
        self.freshness_half_life_days = freshness_half_life_days


class KnowledgeRanker:
    """Composite knowledge result ranker."""

    def __init__(self, config: RankingConfig | None = None) -> None:
        self._config = config or RankingConfig()

    def rank(
        self,
        items: list[KnowledgeItem],
        vector_scores: dict[str, float] | None = None,
        keyword_scores: dict[str, float] | None = None,
        now: datetime | None = None,
    ) -> list[KnowledgeResult]:
        """Compute composite scores and return sorted results."""
        now = now or datetime.now(timezone.utc)
        results = []

        for item in items:
            score = 0.0
            c = self._config

            # Vector score
            vs = vector_scores.get(item.id, 0.0) if vector_scores else 0.0
            score += c.vector_weight * vs

            # Keyword score
            ks = keyword_scores.get(item.id, 0.0) if keyword_scores else 0.0
            score += c.keyword_weight * ks

            # Freshness — exponential decay
            age_days = (now - item.created_at).total_seconds() / 86400
            freshness = math.exp(-math.log(2) * age_days / max(c.freshness_half_life_days, 1))
            score += c.freshness_weight * freshness

            # Importance
            score += c.importance_weight * item.importance

            # Confidence
            score += c.confidence_weight * item.confidence

            results.append(KnowledgeResult(
                item=item,
                score=score,
                rerank_score=None,  # Reserved for LLM reranker
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
