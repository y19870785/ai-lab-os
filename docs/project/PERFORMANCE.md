# 性能历史基线 —— v0.31.0（Mock Mode，Windows）

> 本文件是 v0.31.0 Mock Mode 的历史记录，不代表真实 Provider 或当前版本性能。

## 环境

- OS：Windows 11
- Python：3.10.9
- Mode：Mock，不调用真实 LLM

## 基线指标

| 指标 | 记录值 |
| --- | --- |
| CLI health response | <1ms |
| CLI chat response（mock） | ~1ms |
| Document QA demo | <1s（1 doc） |
| Personal Assistant（3 turns） | <1s |
| Memory save（episodic） | <1ms/item |
| Concurrent requests（10） | <1s total |

## 测试套件

- 647 tests passed；
- Total runtime：约 28s。

## 已知范围

- 真实 LLM latency 取决于 Provider，历史估计 `gpt-4o-mini` 为 1 至 5 秒；
- 小 Collection 的 Chroma search latency 记录为 <100ms；
- 历史测试运行期间的 Memory usage 记录为稳定。
