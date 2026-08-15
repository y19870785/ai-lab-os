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
3. 删除前核对仓库内消费者、公共 API 清单、发布说明与 package exports；若存在受支持的顶层 import 兼容合同，保留转发桩并交由 Owner 决定迁移周期。
4. 按 [Git 工作流](../governance/GIT_WORKFLOW.md) 不在 `main` 上直接清理，需独立分支、审查与授权。

## 收口执行结果（2026-08-14，Owner 授权）

- 已删除顶层 `agents/`（13 文件）、`knowledge/`（20 文件）、`core/agent/`（3 文件）及空桩目录 `workflows/`、`prompts/`。
- `database/` 不在打包范围且无运行时引用，但既有 PILOT 隔离守卫要求该目录存在；clean checkout 不保留空目录，因此保留最小 `database/__init__.py` 兼容标记，不恢复任何数据库实现。
- `pyproject.toml` include 已移除 `agents*`、`knowledge*`、`workflows*`，仅保留 `api*`、`applications*`、`cli*`、`core*`。
- 删除前已复核：无测试、无治理门禁、无核心代码引用这些路径；全部引用均为包内自引用。
- 兼容性决定已按当前仓库证据关闭：`docs/project/PUBLIC_API_INVENTORY.md` 只把 `core/agents`、`core/knowledge` 列为公共 runtime/manager 入口；v0.34/v0.35 Alpha 发布说明只承诺 CLI、API、CEO Assistant 与 `core` canonical 入口，v0.35 未发布 wheel/sdist 附件；顶层包的 `__init__.py` 也只导出 `__version__`，没有稳定 API export 集。因此记录 `NO_SUPPORTED_PUBLIC_IMPORT_CONTRACT_FOR_REMOVED_PACKAGES`。
- 上述结论严格区分三层证据：`no supported in-repository consumer`；`no documented supported public import contract`；`cannot prove absence of every unknown external consumer`。曾被 setuptools 自动发现和源码 docstring 中存在示例，不等于获得长期 import 兼容承诺；若未来出现未知外部消费者，由 Owner 另行决定迁移或 shim，不在本清理 PR 中自行恢复。
- 相关文档已同步：ARCHITECTURE.md 模块树、PROJECT_CONTEXT.md、ADR-005 链接、CAPABILITY_OWNERSHIP.md 状态行。
- 原提交记录全量回归 1868 通过、零失败；本重建分支的结果以本轮独立验证为准。

## 正式文档一致性扫描（2026-08-15）

对当前非归档 Markdown 中的 `agents/`、`knowledge/`、`core/agent/`、`workflows/`、`prompts/` 与 `knowledge/storage/protocol.py` 声明逐项分类：

| 命中 | 分类 | 处理 |
|---|---|---|
| ADR-006 的 `knowledge/storage/protocol.py` Accepted 路径 | CURRENT_CONFLICT | 已在原 ADR 顶部追加可审计 amendment；当前路径固定为 `core/knowledge/protocol.py`、`sqlite_store.py`、`manager.py`，原正文保留为历史 |
| VERSIONING_POLICY 的顶层 `prompts/` 目录树与 v0.33 当前基线 | CURRENT_CONFLICT | 已标记 `REMOVED / NOT_CURRENT_REPOSITORY_STRUCTURE`，目录树改为 FUTURE_PROPOSAL，当前版本对账为 v0.35.0 Alpha |
| RFC-003 顶层 `agents/`、RFC-004 顶层 `knowledge/` | HISTORICAL_CONTEXT / FUTURE_PROPOSAL | RFC 历史正文不批量改写；不作为当前结构或实现证明 |
| ADR-005 的 `core/agent/` 与顶层 `agents` | HISTORICAL_CONTEXT | 已有显著说明：历史类型与当前 `core/agents` 无一对一映射 |
| TECHNICAL_DEBT、CAPABILITY_OWNERSHIP、PROJECT_CONTEXT、REPOSITORY_MAP 中的删除说明 | REMOVAL_RECORD | 保留；这些命中明确描述历史/删除事实或当前 canonical 路径 |
| ARCHITECTURE、PROJECT_STRUCTURE、PUBLIC_API_INVENTORY、TEST_MATRIX 的 `core/agents`/`core/knowledge` | 当前 canonical 路径 | 无冲突，不修改 |

本扫描关闭的是仓库当前正式文档冲突，不声称所有未知外部文档、历史分支或外部消费者不存在；外部兼容性证据边界继续遵循前述三层结论。

## 相关文档

- [能力所有权](CAPABILITY_OWNERSHIP.md)
- [技术债清单](TECHNICAL_DEBT.md)
- [Git 工作流](../governance/GIT_WORKFLOW.md)
