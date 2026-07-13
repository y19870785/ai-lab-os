# Benchmark Report —— v0.22.1

## Environment

- OS: Windows
- Python: 3.10.9
- Date: 2026-07-13

## Results

### Memory Layer

| Operation | Count | Time | Throughput |
|-----------|-------|------|------------|
| save | 1000 | TBD | TBD ops/s |
| retrieve | 500 | TBD | TBD ops/s |
| delete | 500 | TBD | TBD ops/s |

### Provider Layer (Mock)

| Operation | Count | Time | Throughput |
|-----------|-------|------|------------|
| LLM generate | 100 | TBD | TBD req/s |
| LLM stream | 50 | TBD | TBD req/s |

### Stress Test

| Scenario | Count | Time | Status |
|----------|-------|------|--------|
| Memory ops | 1000 | TBD | ✅ |
| Workflow creation | 500 | TBD | ✅ |
| Task creation | 200 | TBD | ✅ |
| Agent requests | 50 | TBD | ✅ |
| Tool calls | 100 | TBD | ✅ |
| Message bus | 200 | TBD | ✅ |

> Note: Detailed timing data available by running `python benchmarks/benchmark_memory.py`
