# ADR-012: Pipeline Architecture for Knowledge Ingestion

## Status
Accepted (2026-07-12)

## Decision
Knowledge ingestion uses a Pipeline Architecture: Reader -> Cleaner -> Normalizer -> Metadata Extractor -> Chunker -> Embedding -> Vector Store. Each step is plug-in and independently testable.

## Rationale
- Monolithic ingest() is not extensible
- Each step should be swappable without touching others
- New parsers (PDF, HTML) plug in as Reader implementations
