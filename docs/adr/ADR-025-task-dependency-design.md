# ADR-025: Task Dependency Design

**状态：** Accepted
**版本：** v0.22.0
**日期：** 2026-07-13

## 上下文

Task 之间需要定义依赖关系（A 在 B 之后执行、C 必须成功 D 才能开始）。需要决定依赖的表达方式和解析策略。

## 决策

**六种依赖类型 + 中心化解析器**：

| 类型 | 含义 | 满足条件 |
|------|------|---------|
| AFTER | 之后执行 | dependee 已结束（COMPLETED/FAILED/CANCELLED） |
| BEFORE | 之前执行 | dependee 未开始（CREATED） |
| ALL_SUCCESS | 全部成功 | dependee == COMPLETED |
| ANY_SUCCESS | 任一成功 | dependee == COMPLETED |
| ALL_FAILED | 全部失败 | dependee == FAILED |
| ANY_FAILED | 任一失败 | dependee == FAILED |
| MANUAL | 手动触发 | 永不自动满足 |

`DependencyResolver` 是纯函数，无副作用，可独立测试。

## 为什么不在 Workflow 层实现依赖

Workflow 的 `depends_on` 只表示步骤间顺序。Task 间依赖涉及跨 Workflow 的状态检查，需要 Task 层的全局视角。

## 后果

- **正面**：六种类型覆盖常见场景、纯函数易测试、为 Multi-Agent 预留接口
- **负面**：不支持循环依赖（设计上禁止）
