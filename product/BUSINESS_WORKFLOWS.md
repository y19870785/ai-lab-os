# CEO Assistant 业务工作流

## 工作记录闭环

```
用户输入自然语言
    ↓
意图识别 (LLM 或规则)
    ↓
实体提取 (日期/对象/事项/状态/标签)
    ↓
结构化存储
    ├── Episodic Memory (原始记录 + 结构化)
    ├── Semantic Memory (实体 + 关系，如需要)
    └── 关联已有 Task/Decision
    ↓
返回结构化确认
```

## 任务闭环

```
创建:
  用户输入 → 提取任务信息 → 创建 Task → 关联工作记录

查询:
  用户查询 → 检索 Task Store → 格式化返回

更新:
  用户操作 → 更新 Task 状态 → 发送事件

完成/取消:
  状态变更 → 记录时间 → 可能写入 Experience Memory
```

## 决策闭环

```
创建:
  用户输入 → 提取决策要素 → 创建 Decision Memory → 关联 Task/Episode

追踪:
  定期检查 → outcome_status 更新 → 成功/失败经验积累

晋升:
  高价值决策 → Consolidation → Knowledge Layer DecisionKnowledge
```

## 知识闭环

```
导入:
  文件 → Reader → Chunker → Embedding → Vector Store → Knowledge Store

检索:
  用户查询 → Embedding → Vector Search + Keyword Search → Hybrid Ranking → 返回引用

更新:
  文档变更 → 重新 Chunk → 重新 Embedding → 更新 Vector Store
```

## 每日简报闭环

```
触发 (CLI/API)
    ↓
查询 Task Store (今日待办/已逾期)
    ↓
查询 Episodic Memory (今日新增工作记录)
    ↓
查询 Decision Memory (最近决策)
    ↓
LLM 组织 → 格式化输出
    ↓
(所有数据来自真实 Store，LLM 只做表达)
```

## Session 闭环

```
创建 Session → 多轮对话 → Memory 写入 (每轮) → Session 过期/关闭
```

## 跨模块数据流

```
工作记录 (Episodic)
    ├── 关联 → Task
    ├── 关联 → Decision
    └── 提取 → Semantic Entity

Task
    ├── 引用 → Episode
    └── 完成 → Experience

Decision
    ├── 引用 → Episode
    ├── 引用 → Task
    └── 晋升 → Knowledge

Knowledge
    └── 引用 → Document
```
