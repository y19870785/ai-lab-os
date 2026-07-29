# Benchmark 历史报告 —— v0.22.1

> 本文件是 v0.22.1 的历史快照，不代表当前性能基线。`TBD` 表示当时未记录具体数据。

## 环境

- OS：Windows
- Python：3.10.9
- 日期：2026-07-13

## 结果

### Memory Layer

| 操作 | 数量 | 时间 | 吞吐量 |
| --- | --- | --- | --- |
| save | 1000 | TBD | TBD ops/s |
| retrieve | 500 | TBD | TBD ops/s |
| delete | 500 | TBD | TBD ops/s |

### Provider Layer（Mock）

| 操作 | 数量 | 时间 | 吞吐量 |
| --- | --- | --- | --- |
| LLM generate | 100 | TBD | TBD req/s |
| LLM stream | 50 | TBD | TBD req/s |

### 压力测试

| 场景 | 数量 | 时间 | 状态 |
| --- | --- | --- | --- |
| Memory ops | 1000 | TBD | ✅ |
| Workflow creation | 500 | TBD | ✅ |
| Task creation | 200 | TBD | ✅ |
| Agent requests | 50 | TBD | ✅ |
| Tool calls | 100 | TBD | ✅ |
| Message bus | 200 | TBD | ✅ |

> 详细计时需要实际运行 `python benchmarks/benchmark_memory.py`；本文件未记录运行结果。
