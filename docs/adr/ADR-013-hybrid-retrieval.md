# ADR-013: Hybrid Retrieval Strategy

## Status
Accepted (2026-07-12)

## Decision
Use Hybrid Retrieval combining vector search (semantic) and keyword search (exact). Default weights: vector 0.7, keyword 0.3. Ranking further boosts freshness, importance, confidence. Future LLM reranker plugs into KnowledgeRanker.

## Rationale
- Vector-only misses exact keyword matches
- Keyword-only lacks semantic understanding
- Hybrid gives best of both worlds
- LLM reranker is future work, not v0.15.0
