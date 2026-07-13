"""Memory Importance Scoring System.

Calculates a composite importance score for each memory item based on:
- Base importance (provided at creation time)
- Frequency of access/update
- Recency of last access
- Confidence score (how reliable the memory is)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from core.memory.models import MemoryItem


@dataclass
class ImportanceConfig:
    """Importance score weight configuration. Sum of all weights should be 1.0."""
    w_base: float = 0.35
    w_frequency: float = 0.25
    w_recency: float = 0.25
    w_confidence: float = 0.15
    frequency_saturation: int = 20
    recency_half_life: float = 86400.0


class ImportanceScorer:
    """Memory importance scorer. Score range: 0.0 ~ 1.0."""

    def __init__(self, config: ImportanceConfig | None = None) -> None:
        self._config = config or ImportanceConfig()
        self._access_counts: dict[str, int] = {}
        self._last_access: dict[str, float] = {}

    def calculate(self, item: MemoryItem, access_count: int | None = None,
                  last_access_ts: float | None = None, now: float | None = None) -> float:
        now = now or time.time()
        base = self._clamp(item.importance, 0.0, 1.0)
        freq = self._frequency_factor(access_count or self._access_counts.get(item.id, 1))
        recency = self._recency_factor(last_access_ts or self._last_access.get(item.id, now), now)
        confidence = self._clamp(float(item.metadata.get("confidence", 0.5)), 0.0, 1.0)
        score = (self._config.w_base * base + self._config.w_frequency * freq
                 + self._config.w_recency * recency + self._config.w_confidence * confidence)
        return self._clamp(score, 0.0, 1.0)

    def record_access(self, memory_id: str, timestamp: float | None = None) -> None:
        now = timestamp or time.time()
        self._access_counts[memory_id] = self._access_counts.get(memory_id, 0) + 1
        self._last_access[memory_id] = now

    def get_access_count(self, memory_id: str) -> int:
        return self._access_counts.get(memory_id, 0)

    def get_last_access(self, memory_id: str) -> float | None:
        return self._last_access.get(memory_id)

    def reset(self, memory_id: str | None = None) -> None:
        if memory_id:
            self._access_counts.pop(memory_id, None)
            self._last_access.pop(memory_id, None)
        else:
            self._access_counts.clear()
            self._last_access.clear()

    def _frequency_factor(self, count: int) -> float:
        k = 3.0 / max(self._config.frequency_saturation, 1)
        return 1.0 - math.exp(-k * count)

    def _recency_factor(self, last_access: float, now: float) -> float:
        delta = max(now - last_access, 0.0)
        half_life = self._config.recency_half_life
        if half_life <= 0:
            return 1.0
        return math.exp(-math.log(2) * delta / half_life)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
