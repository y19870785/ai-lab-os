# AI-Lab Git 工作流

## 分支约定

`main` 是唯一稳定分支，只接收经过测试和审查的变更。禁止直接在 `main` 上开发。

当前允许的分支前缀：

```text
main
  |-- fix/sp-001-single-composition-root
  |-- fix/bootstrap
  |-- fix/database-lifecycle
  `-- review/gpt56-findings
```

- `fix/*`：修复已确认的缺陷，不附带新功能。
- `feature/*`：开发经过批准的新功能。
- `review/*`：独立审查、验证和审查文档。

## 标准流程

```text
从 main 创建分支
-> Codex 修改
-> 执行相关测试和全量回归
-> Commit
-> Push
-> Pull Request
-> 架构审查
-> 合并 main
```

## 强制规则

1. 分支必须从最新 `main` 创建。
2. 一个分支只解决一个明确问题。
3. 提交前必须确认 `.env`、数据库、Chroma、日志和运行数据未被跟踪。
4. Pull Request 必须写明变更范围、根因、验证命令和测试结果。
5. 全量测试存在新增失败时不得合并。
6. 架构边界或公共协议变更必须先提交 RFC/ADR 并通过审查。
7. 禁止在 `main` 上直接进行功能开发、重构或技术债清理。
8. Pull Request 只能由产品负责人在架构审查明确通过后合并。
9. Codex 负责创建和更新 PR，但不得自行合并或移动冻结标签。

## SP-001 审查流程

```text
main@a6f2b62
→ fix/sp-001-single-composition-root
→ 分层提交
→ 推送远程分支
→ 创建 PR（目标 main）
→ ChatGPT 审查真实 Diff
→ APPROVED 后由产品负责人决定合并
```

审查要求覆盖：唯一 Composition Root、CLI/API 共用容器、真实 Application Instance 派发、No Fake Success、持久化测试、全量测试和敏感信息检查。

## 首批建议分支

以下分支仅表示建议顺序，本次发布任务不创建：

1. `fix/sp-001-single-composition-root`
2. `fix/bootstrap`
3. `fix/database-lifecycle`
4. `review/gpt56-findings`
