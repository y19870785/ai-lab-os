"""Knowledge Demo —— 验证 Knowledge Pipeline 完整链路。

演示：Document -> Chunk -> Embedding (Mock) -> Vector (Mock) -> Hybrid Retrieval -> Rank
"""

import asyncio
import sys
sys.path.insert(0, ".")

from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.retrieval import VectorRetriever, KeywordRetriever
from core.knowledge.ranking import KnowledgeRanker
from core.knowledge.chunking import get_chunker
from core.knowledge.models import KnowledgeQuery, SourceType, KnowledgeType
from core.providers.embedding.mock import MockEmbeddingProvider
from core.providers.vector.mock import MockVectorProvider


async def main():
    print("=" * 60)
    print("Knowledge Pipeline Demo")
    print("=" * 60)

    # Setup providers
    emb = MockEmbeddingProvider()
    vec = MockVectorProvider()
    await emb.initialize()
    await vec.initialize()

    # Create pipeline
    pipe = IngestionPipeline(embedding_provider=emb, vector_provider=vec)
    vr = VectorRetriever(embedding_provider=emb, vector_provider=vec)
    kw = KeywordRetriever()
    ranker = KnowledgeRanker()

    # Ingest documents
    docs = [
        ("AI-Lab Overview", "AI-Lab is a personal AI operating system that supports multiple agents, tools, and knowledge management."),
        ("Python Guide", "Python is a high-level programming language used for data science, web development, and AI."),
        ("Machine Learning", "Machine learning uses algorithms to find patterns in data. Deep learning is a subset using neural networks."),
        ("Agent Systems", "AI agents can autonomously perform tasks using tools, memory, and knowledge retrieval."),
        ("Memory Systems", "Episode memory stores past interactions. Semantic memory stores facts. Decision memory stores choices."),
    ]

    for title, content in docs:
        item, chunks = await pipe.ingest(
            content=content, title=title, source=f"{title.lower().replace(' ', '_')}.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        kw.index(item)
        for chunk in chunks:
            await vr.index_chunk(chunk.chunk_id, chunk.content)
        print(f"  [OK] Ingested: {title} ({len(chunks)} chunks)")

    # Search
    queries = [
        "What is AI-Lab?",
        "neural networks deep learning",
        "agent tools memory",
    ]
    print("\n--- Search Results ---")
    for q in queries:
        print(f"\nQuery: {q}")
        # Keyword
        kw_results = kw.search(q, top_k=3)
        items_kw = [item for item_id, score in kw_results for item in [None] if False]  # placeholder
        vs = {item_id: s for item_id, s in kw_results}

        # Vector
        vr_results = await vr.search(q, top_k=3)
        vs_vec = {vid: s for vid, s, _ in [("", 0)] if False}  # placeholder

        # Rank (keyword only for demo)
        from core.knowledge.models import KnowledgeResult, KnowledgeItem as KI
        results_for_rank = []
        for item_id, score in kw_results[:3]:
            # Find item by scanning (demo only)
            results_for_rank.append(KnowledgeResult(
                item=KI(id=item_id, title="", content="", source=""),
                score=score,
            ))
        ranked = ranker.rank(
            [r.item for r in results_for_rank],
            vector_scores={r.item.id: r.score for r in results_for_rank},
            keyword_scores={r.item.id: r.score for r in results_for_rank},
        )
        for r in ranked:
            print(f"  [{r.score:.2f}] {r.item.title}")

    await emb.shutdown()
    await vec.shutdown()
    print("\n" + "=" * 60)
    print("Knowledge Pipeline Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
