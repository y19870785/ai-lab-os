"""Consolidation Policy.

Defines the actions that can be taken on memories during consolidation:
- RETAIN: Keep the memory as-is (high importance, recent)
- COMPRESS: Summarize/compress the memory (medium importance, older)
- PROMOTE: Elevate to Knowledge Layer (high importance, cross-session)
- DELETE: Remove the memory (decayed, low importance)

Each policy decision is based on importance score, decay factor, and
memory type.

Usage:
    from core.memory.policy import ConsolidationPolicy, PolicyDecision, ConsolidationAction

    policy = ConsolidationPolicy()
    decision = policy.evaluate(item, importance_score=0.8, decay_factor=0.5)
    if decision.action == ConsolidationAction.PROMOTE:
        # promote to knowledge
    elif decision.action == ConsolidationAction.COMPRESS:
        # compress
    elif decision.action == ConsolidationAction.DELETE:
        # delete
    # else: RETAIN
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.memory.models import MemoryItem, MemoryType


class ConsolidationAction(str, Enum):
    """Actions that can be taken during memory consolidation."""
    RETAIN = "retain"
    COMPRESS = "compress"
    PROMOTE = "promote"
    DELETE = "delete"


@dataclass
class PolicyDecision:
    """Result of evaluating a memory against consolidation policy."""
    memory_id: str
    memory_type: MemoryType
    action: ConsolidationAction
    score: float
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsolidationThresholds:
    """Thresholds for consolidation actions.

    promote_min_score: Minimum importance score to promote to Knowledge.
    compress_max_score: Below this score, memory may be compressed.
    delete_max_score: Below this score, memory may be deleted.
    promote_min_access: Minimum access count to consider promotion.
    """
    promote_min_score: float = 0.75
    compress_max_score: float = 0.45
    delete_max_score: float = 0.20
    promote_min_access: int = 3


class ConsolidationPolicy:
    """Memory consolidation policy engine.

    Evaluates each memory and determines what action to take based on:
    - Importance score (how valuable is this memory)
    - Decay factor (how old / stale)
    - Memory type (session vs episodic vs semantic vs decision)
    - Cross-session patterns (is this knowledge-worthy)
    """

    def __init__(self, thresholds: ConsolidationThresholds | None = None) -> None:
        self._thresholds = thresholds or ConsolidationThresholds()

    def evaluate(
        self,
        item: MemoryItem,
        importance_score: float,
        decay_factor: float,
        access_count: int = 1,
    ) -> PolicyDecision:
        """Evaluate a memory and return a consolidation decision.

        Args:
            item: The memory item to evaluate.
            importance_score: Current importance score (0.0 ~ 1.0).
            decay_factor: Current decay factor (0.0 ~ 1.0, 1.0 = fresh).
            access_count: How many times this memory was accessed.

        Returns:
            PolicyDecision with action and reasoning.
        """
        effective = importance_score * decay_factor
        reasons: list[str] = []
        t = self._thresholds

        # ── Decision logic ──

        # Session memories: always delete or retain (never promote directly)
        if item.memory_type == MemoryType.SESSION:
            if effective < t.delete_max_score or decay_factor < 0.1:
                reasons.append(f"Session memory decayed below delete threshold ({effective:.2f})")
                return PolicyDecision(
                    memory_id=item.id, memory_type=item.memory_type,
                    action=ConsolidationAction.DELETE, score=effective, reasons=reasons,
                )
            reasons.append(f"Session memory above decay threshold ({effective:.2f})")
            return PolicyDecision(
                memory_id=item.id, memory_type=item.memory_type,
                action=ConsolidationAction.RETAIN, score=effective, reasons=reasons,
            )

        # ── Episodic / Semantic / Decision ──

        # High importance + high access + fresh -> promote to knowledge
        if (importance_score >= t.promote_min_score
                and access_count >= t.promote_min_access
                and decay_factor > 0.5):
            reasons.append(
                f"High importance ({importance_score:.2f}), "
                f"accessed {access_count} times, promoting to knowledge"
            )
            return PolicyDecision(
                memory_id=item.id, memory_type=item.memory_type,
                action=ConsolidationAction.PROMOTE, score=effective, reasons=reasons,
            )

        # High importance + fresh -> retain
        if effective > t.compress_max_score:
            reasons.append(f"Effective score {effective:.2f} above compress threshold, retaining")
            return PolicyDecision(
                memory_id=item.id, memory_type=item.memory_type,
                action=ConsolidationAction.RETAIN, score=effective, reasons=reasons,
            )

        # Medium importance -> compress
        if effective > t.delete_max_score:
            reasons.append(f"Effective score {effective:.2f} in compress range, compressing")
            return PolicyDecision(
                memory_id=item.id, memory_type=item.memory_type,
                action=ConsolidationAction.COMPRESS, score=effective, reasons=reasons,
            )

        # Low importance + decayed -> delete
        reasons.append(f"Effective score {effective:.2f} below delete threshold, deleting")
        return PolicyDecision(
            memory_id=item.id, memory_type=item.memory_type,
            action=ConsolidationAction.DELETE, score=effective, reasons=reasons,
        )

    def evaluate_batch(
        self,
        items: list[tuple[MemoryItem, float, float, int]],
    ) -> list[PolicyDecision]:
        """Evaluate multiple memories at once.

        Args:
            items: List of (MemoryItem, importance_score, decay_factor, access_count) tuples.

        Returns:
            List of PolicyDecision, one per item.
        """
        return [self.evaluate(item, score, decay, count)
                for item, score, decay, count in items]

    @property
    def thresholds(self) -> ConsolidationThresholds:
        return self._thresholds
