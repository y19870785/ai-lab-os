# Performance Baseline —— v0.31.0 (Mock Mode, Windows)

## Environment
- OS: Windows 11
- Python: 3.10.9
- Mode: Mock (no real LLM calls)

## Baseline Metrics

| Metric | Value |
|--------|-------|
| CLI health response | <1ms |
| CLI chat response (mock) | ~1ms |
| Document QA demo | <1s (1 doc) |
| Personal Assistant (3 turns) | <1s |
| Memory save (episodic) | <1ms/item |
| Concurrent requests (10) | <1s total |

## Test Suite
- 647 tests passed
- Total runtime: ~28s

## Known
- Real LLM latency depends on provider (typically 1-5s for gpt-4o-mini)
- Chroma search latency <100ms for small collections
- Memory usage stable during test runs
