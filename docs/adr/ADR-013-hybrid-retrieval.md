# ADR-013：混合检索策略

## 状态

Accepted（2026-07-12）

## 决策

采用结合向量搜索（语义）与关键词搜索（精确）的混合检索。默认权重为向量 0.7、关键词
0.3，并根据 freshness、importance 与 confidence 进一步调整排序。未来的 LLM reranker
通过 `KnowledgeRanker` 接入。

## 理由

- 仅使用向量搜索可能漏掉精确关键词；
- 仅使用关键词搜索缺少语义理解；
- 混合检索兼顾两类能力；
- LLM reranker 属于未来工作，不属于 v0.15.0。
