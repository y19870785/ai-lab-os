"""Memory Decay System.

Calculates time-based decay for memories.
Uses exponential decay formula with configurable half-life.

The decay factor determines how much a memory's strength has diminished
over time. This feeds into the consolidation policy's decisions.

Usage:
    from core.memory.decay import MemoryDecay, DecayConfig

    decay = MemoryDecay()
    factor = decay.calculate(created_at=some_timestamp)
    is_expired = decay.is_expired(item)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from core.memory.models import MemoryItem


@dataclass
class DecayConfig:
    """Decay configuration.

    half_life: Seconds after which memory strength decays to 50%.
    min_strength: Minimum strength before memory is considered "decayed".
    """
    half_life: float = 86400.0       # 24 hours
    min_strength: float = 0.05       # 5% = considered decayed
    max_decay_seconds: float = 7776000.0  # 90 days cap


class MemoryDecay:
    """Memory decay calculator.

    Uses exponential decay: strength = e^(-ln(2) * delta / half_life)
    """

    def __init__(self, config: DecayConfig | None = None) -> None:
        self._config = config or DecayConfig()

    def calculate(self, created_at: float, now: float | None = None) -> float:
        """Calculate decay factor for a memory based on its age.

        Returns a strength value between 0.0 and 1.0.
        1.0 = brand new, 0.0 = fully decayed.
        """
        now = now or time.time()
        delta = max(now - created_at, 0.0)
        delta = min(delta, self._config.max_decay_seconds)
        half_life = self._config.half_life

        if half_life <= 0:
            return 1.0

        return math.exp(-math.log(2) * delta / half_life)

    def calculate_from_item(self, item: MemoryItem, now: float | None = None) -> float:
        """Calculate decay factor from a MemoryItem's timestamp."""
        ts = item.timestamp.timestamp() if hasattr(item.timestamp, 'timestamp') else time.time()
        return self.calculate(ts, now)

    def is_decayed(self, item: MemoryItem, now: float | None = None) -> bool:
        """Check if a memory has decayed below minimum strength."""
        strength = self.calculate_from_item(item, now)
        return strength < self._config.min_strength

    def effective_strength(self, item: MemoryItem, importance: float,
                           now: float | None = None) -> float:
        """Combined effective strength = importance * decay_factor."""
        decay = self.calculate_from_item(item, now)
        return importance * decay

    def time_until_decay(self, created_at: float) -> float | None:
        """Seconds until this memory reaches min_strength, or None if already decayed."""
        strength = self.calculate(created_at)
        if strength < self._config.min_strength:
            return 0.0

        half_life = self._config.half_life
        min_strength = self._config.min_strength

        # Solve: min_strength = e^(-ln(2) * t / half_life)
        # t = -half_life * ln(min_strength) / ln(2)
        total_time = -half_life * math.log(min_strength) / math.log(2)
        elapsed = time.time() - created_at
        remaining = total_time - elapsed
        return max(0.0, remaining)

    @property
    def config(self) -> DecayConfig:
        return self._config
