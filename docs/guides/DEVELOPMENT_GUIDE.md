
# AI-Lab Development Guide

## 开发流程

### 1. 文档驱动开发

所有功能开发前先写文档：

- 新功能 / 重大变更 → 先写 **RFC**（`docs/rfc/`）
- 架构决策 → 记录 **ADR**（`docs/adr/`）
- 接口 / 用法 → 更新对应文档

### 2. RFC 流程

1. 在 `docs/rfc/` 下创建 `YYYY-MM-DD-title.md`
2. 描述背景、方案、可选方案
3. 评审 → 定稿 → 实施
4. 实施完成后 RFC 归档（可关闭或标记为已实现）

### 3. ADR 记录

每个重要架构决策在 `docs/adr/` 下记录：

- `ADR-001-项目结构约定.md`
- `ADR-002-配置管理方案.md`

格式：标题、背景、决策、后果。

### 4. 代码规范

- **Python 3.11+**
- 类型注解（Type Hints）必须完整
- 函数/类需有 docstring（Google 风格）
- 遵循 PEP 8

### 5. 分支策略

```
main        → 稳定版本
dev         → 开发分支
feature/*   → 功能分支
fix/*       → 修复分支
```

### 6. 配置管理

- 默认配置在 `config/default.yaml`
- 敏感信息走环境变量（`.env`）
- 不要提交 `.env` 到版本控制

### 7. 日志规范

结构化 JSON 日志，分级：

- DEBUG / INFO / WARNING / ERROR

---
