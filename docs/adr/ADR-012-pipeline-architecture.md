# ADR-012：Knowledge 摄取管线架构

## 状态

Accepted（2026-07-12）

## 决策

Knowledge 摄取采用 Pipeline Architecture：

```text
Reader -> Cleaner -> Normalizer -> Metadata Extractor
-> Chunker -> Embedding -> Vector Store
```

每一步都可插拔并可独立测试。

## 理由

- 单体 `ingest()` 难以扩展；
- 每一步都应在不修改其他步骤的情况下替换；
- PDF、HTML 等新解析器可作为 Reader 实现接入。
