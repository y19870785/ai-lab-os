"""Tests for knowledge ranking."""
import pytest
from datetime import datetime, timezone, timedelta
from core.knowledge.models import KnowledgeItem, KnowledgeResult
from core.knowledge.ranking import KnowledgeRanker, RankingConfig


class TestKnowledgeRanker:
    def test_basic_ranking(self):
        ranker = KnowledgeRanker()
        items = [
            KnowledgeItem(id="a", title="A", content="aaa", importance=0.9, confidence=0.8),
            KnowledgeItem(id="b", title="B", content="bbb", importance=0.3, confidence=0.5),
        ]
        results = ranker.rank(items)
        assert len(results) == 2
        assert results[0].item.id == "a"  # Higher importance wins
        assert results[0].score > results[1].score

    def test_with_vector_scores(self):
        ranker = KnowledgeRanker()
        items = [KnowledgeItem(id="a", title="A", content="a"), KnowledgeItem(id="b", title="B", content="b")]
        vec_scores = {"a": 0.9, "b": 0.3}
        results = ranker.rank(items, vector_scores=vec_scores)
        assert results[0].item.id == "a"

    def test_freshness_decay(self):
        ranker = KnowledgeRanker(RankingConfig(freshness_half_life_days=30))
        old = KnowledgeItem(id="old", title="Old", content="old", created_at=datetime.now(timezone.utc) - timedelta(days=60))
        new = KnowledgeItem(id="new", title="New", content="new", created_at=datetime.now(timezone.utc))
        results = ranker.rank([old, new])
        assert results[0].item.id == "new"
