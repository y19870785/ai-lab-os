# Alpha 发布检查清单 — v0.34.0

## 候选版本准备

- [x] `pyproject.toml` 源版本设为 `0.34.0`
- [x] `project_state.json` 记录 SP-014 / SP-014B / ACC-014 最终状态
- [x] SP-015、SP-015A 与 SP-015R 已封存；SP-016 当时仍仅为候选
- [x] README、Project Brain、Roadmap、Changelog 与 v0.34.0 Alpha 发布说明的职责已完成对账
- [x] SP-015 未增加业务行为或数据库 Schema Migration

## 必需验证

- [x] 治理一致性测试通过
- [x] 完整 non-real pytest 门禁通过
- [x] 变更的 Python 文件通过 Ruff
- [x] Source distribution 与 wheel 构建成功
- [x] 构建产物报告版本 `0.34.0`
- [x] 全新 wheel 安装报告的运行时与 distribution metadata 版本均为 `0.34.0`
- [x] SP-015A main Quality Gate run `29749469117` 通过
- [x] SP-015R Draft PR Quality Gate run `29750558338` 通过

## 发布门禁

- [x] SP-015 已批准并合并
- [x] SP-015 合并后的 main Quality Gate 通过
- [x] 合并后验收完成
- [x] SP-015A 已合并，且其 main Quality Gate 通过
- [x] Release 对账实施完成
- [x] SP-015R 已合并，且 main Quality Gate run `29855987444` 通过
- [x] Owner 与 ChatGPT 已授权发布 v0.34.0
- [x] 最终发布提交已准备

外部发布验证以 GitHub Tag 与 GitHub Release 为权威来源。本发布提交合并后，应从外部核验 `v0.34.0`。获授权的 GitHub Release 是未上传 wheel 或 sdist 的 Pre-release；本清单不要求为发布后状态再创建仓库提交。
