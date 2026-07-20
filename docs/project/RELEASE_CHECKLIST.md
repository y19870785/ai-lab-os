# Alpha Release Checklist — v0.34.0

## Candidate preparation

- [x] `pyproject.toml` source version set to `0.34.0`
- [x] `project_state.json` records SP-014 / SP-014B / ACC-014 final state
- [x] SP-015 archived after post-merge acceptance; SP-015A is in Draft reconciliation; SP-016 remains candidate only
- [x] README、Project Brain、Roadmap、Changelog 与 v0.34.0 Alpha release notes responsibilities reconciled
- [x] No business behavior or database schema migration added by SP-015

## Required verification

- [x] Governance consistency tests pass
- [x] Full non-real pytest gate passes
- [x] Changed Python files pass Ruff
- [x] Source distribution and wheel build successfully
- [x] Built artifacts report version `0.34.0`
- [x] Fresh wheel installation reports runtime and distribution metadata version `0.34.0`
- [x] SP-015 main Quality Gate run `29738408215` passes
- [ ] Draft PR Quality Gate passes

## Publication gates

- [x] SP-015 approved and merged
- [x] Main Quality Gate passes after SP-015 merge
- [x] Post-merge acceptance completed
- [ ] Release reconciliation completed
- [ ] SP-015A merged and its main Quality Gate passes
- [ ] Owner and ChatGPT authorize Tag and GitHub Release creation
- [ ] `v0.34.0` Tag created from the approved commit
- [ ] GitHub Release published from the same Tag

未完成 Publication gates 前，源码中的 `0.34.0` 只能称为 Alpha Candidate，不得宣称 v0.34.0 已正式发布。
