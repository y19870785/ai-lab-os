# Alpha Release Checklist — v0.34.0

## Candidate preparation

- [x] `pyproject.toml` source version set to `0.34.0`
- [x] `project_state.json` records SP-014 / SP-014B / ACC-014 final state
- [x] SP-015, SP-015A and SP-015R archived; SP-016 remains candidate only
- [x] README、Project Brain、Roadmap、Changelog 与 v0.34.0 Alpha release notes responsibilities reconciled
- [x] No business behavior or database schema migration added by SP-015

## Required verification

- [x] Governance consistency tests pass
- [x] Full non-real pytest gate passes
- [x] Changed Python files pass Ruff
- [x] Source distribution and wheel build successfully
- [x] Built artifacts report version `0.34.0`
- [x] Fresh wheel installation reports runtime and distribution metadata version `0.34.0`
- [x] SP-015A main Quality Gate run `29749469117` passes
- [x] SP-015R Draft PR Quality Gate passes — run `29750558338`

## Publication gates

- [x] SP-015 approved and merged
- [x] Main Quality Gate passes after SP-015 merge
- [x] Post-merge acceptance completed
- [x] SP-015A merged and its main Quality Gate passes
- [x] Release reconciliation implementation completed
- [x] SP-015R merged and its main Quality Gate passes — run `29855987444`
- [x] Owner and ChatGPT authorize v0.34.0 publication
- [x] Final publication commit prepared

External publication verification: GitHub Tag and GitHub Release are authoritative. Verify `v0.34.0` externally after this publication commit is merged. The authorized GitHub Release is a Pre-release with no uploaded wheel or sdist; this checklist does not require a post-publication repository commit.
