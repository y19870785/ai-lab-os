"""Document QA Demo —— 真实 Knowledge Pipeline 验证。

Usage:
    python examples/field_validation/document_qa/run.py
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


async def main():
    print("=" * 60)
    print("Field Validation: Document QA Demo")
    print("=" * 60)

    from core.knowledge.ingestion import IngestionPipeline
    from core.knowledge.retrieval import VectorRetriever, KeywordRetriever
    from core.knowledge.ranking import KnowledgeRanker
    from core.knowledge.models import KnowledgeQuery, SourceType, KnowledgeType

    # Embedding: always use local SentenceTransformer (DeepSeek has no embedding API)
    print("\n[Embedding] Using local SentenceTransformer")
    from core.providers.embedding.local import LocalEmbeddingProvider
    emb = LocalEmbeddingProvider(
        model_name=os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        device=os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu"),
    )

    # Vector: use Chroma if available, else mock
    use_chroma = True
    try:
        from core.providers.vector.chroma import ChromaVectorProvider
        vec = ChromaVectorProvider()
        print("[Vector] Using Chroma")
    except Exception:
        from core.providers.vector.mock import MockVectorProvider
        vec = MockVectorProvider()
        use_chroma = False
        print("[Vector] Using Mock (Chroma unavailable)")

    await emb.initialize()
    await vec.initialize()

    pipe = IngestionPipeline(embedding_provider=emb, vector_provider=vec)
    vr = VectorRetriever(embedding_provider=emb, vector_provider=vec)
    kw = KeywordRetriever()
    ranker = KnowledgeRanker()

    # Load sample documents
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_documents")
    doc_count = 0
    if os.path.isdir(sample_dir):
        for fname in os.listdir(sample_dir):
            if fname.endswith(".md") or fname.endswith(".txt"):
                fpath = os.path.join(sample_dir, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                st = SourceType.MARKDOWN if fname.endswith(".md") else SourceType.PLAINTEXT
                item, chunks = await pipe.ingest(
                    content=content, title=fname, source=fname,
                    source_type=st, knowledge_type=KnowledgeType.DOCUMENT,
                )
                kw.index(item)
                for chunk in chunks:
                    await vr.index_chunk(chunk.chunk_id, chunk.content)
                print(f"  [OK] Ingested: {fname} ({len(chunks)} chunks)")
                doc_count += 1

    if doc_count == 0:
        print("  [WARN] No documents found in sample_documents/")

    # Query
    queries = ["What is AI-Lab?", "Memory Layer", "REST API"]
    print("\n--- Query Results ---")
    for q in queries:
        vr_results = await vr.search(q, top_k=3)
        kw_results = kw.search(q, top_k=3)
        print(f"\nQuery: {q}")
        print(f"  Vector results: {len(vr_results)}")
        if vr_results:
            top = vr_results[0]
            score = getattr(top, 'score', None)
            if score is not None:
                print(f"  Top vector score: {score:.4f}")
            if hasattr(top, 'content'):
                print(f"  Top snippet: {top.content[:100]}...")
        print(f"  Keyword results: {len(kw_results)}")

    emb_dim = emb.dimension()
    print(f"\nEmbedding dimension: {emb_dim}")

    await emb.shutdown()
    await vec.shutdown()
    print("\n" + "=" * 60)
    print(f"Document QA Demo Complete [REAL Embedding + {'Chroma' if use_chroma else 'Mock'} Vector]")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
