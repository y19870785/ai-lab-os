# AI-Lab 重复实现弃用审计

> 日期：2026-08-14
> 重建来源：`6d2b40d` 弃用审计与 `8967e20` 重复实现收口
> 性质：GOV-RECOVERY-001-R2 授权的独立技术债重建；不构成 Ready 或 Merge 授权。

## 审计范围

清点 [能力所有权](CAPABILITY_OWNERSHIP.md) 标记为 DEPRECATION_CANDIDATE 的重复实现：顶层 `agents/`、`knowledge/`、`core/agent/` 的引用关系、打包范围与工作区草稿文件。

## 引用关系审计

| 模块 | 文件数 | 外部引用 | 判定 |
| --- | --- | --- | --- |
| `agents/`（顶层） | 13 | 无（仅自身内部 import） | 死代码 / DEPRECATION_CANDIDATE |
| `core/agent/` | 3 | 无（仅自身内部 import） | 死代码 / DEPRECATION_CANDIDATE |
| `core/agents/` | 12 | 有（core/system、core/workflow、examples、tests） | 在用实现 |
| `knowledge/`（顶层） | 20 | 无（仅自身内部 import） | 死代码 / DEPRECATION_CANDIDATE |
| `core/knowledge/` | 14 | 有（core/system、core/agents/executor、examples、tests） | 在用实现 |
| `workflows/`（顶层） | 1 | 无（空 `__init__.py` 桩） | 空桩 |
| `prompts/`（顶层） | 1 | 无（空 `__init__.py` 桩） | 空桩 |
| `database/`（顶层） | 1 | 无（空 `__init__.py` 桩） | 空桩 |

说明：`agents.identity`、`agents.tools`、`knowledge.models` 等引用全部发生在各自包内部；`core.agents` 与 `core.knowledge` 是正式入口（如 `core/system/factory.py`、`core/agents/executor.py`）实际使用的实现。

## 打包范围审计

`pyproject.toml` 的 `[tool.setuptools.packages.find]` 当前 include `agents*`、`knowledge*`、`workflows*`，会把上述死代码与空桩打包进发布产物；`prompts*` 与 `database*` 未在 include 中，不打包。

## 工作区草稿文件

仓库根目录存在未跟踪草稿文件（`_fix_test.py`、`_phase23_writer.py`、`_p27_0.b64` 至 `_p27_6.b64`、`_p27_all.b64`），已确认均不在 `git ls-files` 中；本轮已清理，不进入版本库。

## 收口建议（需独立授权）

1. 在独立任务与 Owner 授权后，将 `agents*`、`knowledge*`、`workflows*` 移出 pyproject include。
2. 以 `core/agents`、`core/knowledge` 为唯一实现，删除顶层 `agents/`、`knowledge/`、`core/agent/` 与不受现行守卫要求的空桩目录。
3. 删除前先确认无历史分支或外部消费者依赖顶层包名；若存在兼容需求，保留顶层 `__init__.py` 转发桩一段时间。
4. 按 [Git 工作流](../governance/GIT_WORKFLOW.md) 不在 `main` 上直接清理，需独立分支、审查与授权。

## 收口执行结果（2026-08-14，Owner 授权）

- 已删除顶层 `agents/`（13 文件）、`knowledge/`（20 文件）、`core/agent/`（3 文件）及空桩目录 `workflows/`、`prompts/`。
- `database/` 不在打包范围且无运行时引用，但既有 PILOT 隔离守卫要求该目录存在；clean checkout 不保留空目录，因此保留最小 `database/__init__.py` 兼容标记，不恢复任何数据库实现。
- `pyproject.toml` include 已移除 `agents*`、`knowledge*`、`workflows*`，仅保留 `api*`、`applications*`、`cli*`、`core*`。
- 删除前已复核：无测试、无治理门禁、无核心代码引用这些路径；全部引用均为包内自引用。
- 相关文档已同步：ARCHITECTURE.md 模块树、PROJECT_CONTEXT.md、ADR-005 链接、CAPABILITY_OWNERSHIP.md 状态行。
- 原提交记录全量回归 1868 通过、零失败；本重建分支的结果以本轮独立验证为准。

## 相关文档

- [能力所有权](CAPABILITY_OWNERSHIP.md)
- [技术债清单](TECHNICAL_DEBT.md)
- [Git 工作流](../governance/GIT_WORKFLOW.md)
