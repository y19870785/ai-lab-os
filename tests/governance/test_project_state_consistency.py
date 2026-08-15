from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

from core.errors.codes import ErrorCategory

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "project_state.json"
PILOT_001_STATUS = (
    "PLANNING_BASELINE_APPROVED / FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED / "
    "P0_E_ENVIRONMENT_READY / P0_R_IMPLEMENTATION_AUTHORIZED / "
    "P0_R_IMPLEMENTED / P0_R_FINAL_INDEPENDENT_REVIEW_PASSED / "
    "PREVIEW_AUTHORITY_ESTABLISHED / FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED / "
    "PHASE_0_STOPPED_PENDING_INGRESS_BRIDGE_DESIGN / "
    "INGRESS_EVIDENCE_BRIDGE_DESIGN_APPROVED / "
    "INGRESS_EVIDENCE_BRIDGE_FINAL_INDEPENDENT_REVIEW_PASSED / "
    "RFC_033_ADOPTED / ADR_073_ACCEPTED / PILOT_001_IB_IMP_A_AUTHORIZED / "
    "PILOT_001_IB_IMP_A_STOPPED_SIGNING_ORACLE_ISOLATION_FAILED / "
    "PILOT_001_IB_IMP_A_FINAL_CLASSIFICATION_UNSUPPORTED / "
    "PILOT_001_IB_IMP_A_FINAL_INDEPENDENT_SECURITY_REVIEW_PASSED / "
    "PILOT_001_IB_IMP_A_NEGATIVE_EVIDENCE_BASELINE_APPROVED / "
    "INGRESS_PROCESS_ISOLATION_UNRESOLVED / BRIDGE_IMPLEMENTATION_NOT_AUTHORIZED / "
    "PHASE_1_NOT_AUTHORIZED / PILOT_001_P1A_INTERNAL_CONFIRMATION_AUTHORIZED / "
    "PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE / "
    "INTERNAL_PILOT_TRUSTED_CONFIRMATION_PROVEN / "
    "PRODUCTION_PROCESS_ISOLATION_UNRESOLVED / PHASE_1_FULL_NOT_AUTHORIZED / "
    "PHASE_2_NOT_AUTHORIZED / REAL_BUSINESS_MUTATION_NOT_AUTHORIZED / "
    "PILOT_001_P1A_MERGED / PILOT_001_P1A_MAIN_QUALITY_GATE_PASSED / "
    "PILOT_001_P1A_FINAL_INDEPENDENT_REVIEW_PASSED / "
    "PILOT_001_P1A_POST_MERGE_VERIFIED / PILOT_001_P1A_RECONCILED / "
    "PILOT_001_P1A_ARCHIVED / PILOT_001_P1B_PROCESS_ISOLATION_MITIGATION_PROVEN / "
    "PILOT_GRADE_LOCAL_PROCESS_ISOLATED_PROFILE_V1 / "
    "PILOT_PROCESS_ISOLATION_PROVEN_FOR_SUPPORTED_PROFILE / PILOT_001_P1B_ACTUAL_HERMES_RUNTIME_ENTRY_PROVEN"
)


def _load_state() -> dict[str, object]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _sp_number(sp_id: str) -> int:
    match = re.fullmatch(r"SP-(\d+)[A-Z]?", sp_id)
    assert match is not None, f"invalid SP identifier: {sp_id}"
    return int(match.group(1))


def test_runtime_and_governance_versions_are_consistent() -> None:
    state = _load_state()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime_version = pyproject["project"]["version"]

    assert runtime_version == "0.35.0"
    assert state["current_version"] == runtime_version
    assert state["version"] == f"v{runtime_version}"
    assert state["release_status"]["current_version"] == runtime_version


def test_human_facing_current_state_markers_match_project_state() -> None:
    state = _load_state()
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
    brain = (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(encoding="utf-8-sig")

    assert f"v{state['current_version']} Alpha / GitHub Pre-release Published" in readme
    assert f"产品版本：{state['version']}" in brain
    assert f"最近完成的 Product SP：{state['latest_completed_sp']}" in brain
    assert f"当前 Product SP：{state['current_sp']}" in brain
    assert f"当前治理任务：{state['current_governance_task']}" in brain
    assert f"下一候选 Product SP：{state['next_candidate_sp']}" in brain
    baseline = state["verified_release_baseline"]
    assert baseline["commit"] in brain
    assert str(baseline["quality_gate_run"]) in brain


def test_verified_release_baseline_and_sp_progression_are_well_formed() -> None:
    state = _load_state()
    baseline = state["verified_release_baseline"]

    assert "next_action" not in state
    assert "main_commit" not in state
    assert re.fullmatch(r"[0-9a-f]{40}", baseline["commit"])
    assert baseline == {
        "commit": "22f88d1da962fb436c48c19e5343fad8bf62f5f6",
        "quality_gate_run": 29855987444,
        "meaning": (
            "Main commit independently verified before the final publication commit"
        ),
    }

    records = state["sp_records"]
    completed_numbers = [
        _sp_number(sp_id)
        for sp_id, record in records.items()
        if "ARCHIVED" in record["status"]
    ]
    assert _sp_number(state["latest_completed_sp"]) == max(completed_numbers)

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["git_branch"] == "main"
    assert state["next_candidate_sp"] is None


def test_sp015_release_baseline_is_archived_while_sp020_is_latest_work() -> None:
    state = _load_state()
    sp015 = state["sp_records"]["SP-015"]

    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert sp015["status"] == (
        "APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
    )
    assert sp015["pr"] == 35
    assert sp015["approved_head"] == "b69b6dac0e34a5a0d6d216282d10f061c9cac7b3"
    assert sp015["merge_commit"] == "01166352224ddce5e859d4133f502aee1f97da07"
    assert sp015["merged_at"] == "2026-07-20T11:23:58Z"
    assert sp015["post_merge_acceptance"] == "PASSED"
    assert state["quality_gate"]["official"] == {
        "source": "GitHub Actions Quality Gate",
        "run_id": 29855987444,
        "head_sha": "22f88d1da962fb436c48c19e5343fad8bf62f5f6",
        "environment": "ubuntu-latest / Python 3.12",
        "command": 'python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no',
        "ruff": "SUCCESS",
        "pytest": "SUCCESS",
        "passed": 1163,
        "skipped": 6,
        "warnings": 27,
        "exit_code": 0,
        "real_provider_tests_included": False,
    }


def test_sp014_and_acc014_final_state_is_complete() -> None:
    state = _load_state()
    records = state["sp_records"]
    sp014 = records["SP-014"]
    sp014b = records["SP-014B"]
    acceptance = state["acceptance_records"]["ACC-014"]

    assert sp014["status"] == (
        "APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
    )
    assert sp014b["status"] == "APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED"
    assert sp014["acceptance"] == "ACC-014 A-L PASSED / FINAL"
    assert acceptance["status"] == "PASSED / FINAL"
    assert acceptance["scenarios"] == {letter: "PASSED" for letter in "ABCDEFGHIJKL"}


def test_sp015a_sp015r_and_sp016_implementation_state_is_consistent() -> None:
    state = _load_state()
    records = state["sp_records"]
    sp016_name = "Canonical Waiting-For Domain & Agenda Closure"
    sp016_status = (
        "APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / "
        "MANUAL_ACCEPTANCE_PASSED / COMPLETED / ARCHIVED"
    )
    sp015a_status = "APPROVED / MERGED / RECONCILED / ARCHIVED"
    sp015r_status = "APPROVED / MERGED / RECONCILED / ARCHIVED"

    assert records["SP-015A"]["status"] == sp015a_status
    assert records["SP-015A"]["approved"] is True
    assert records["SP-015A"]["implementation_started"] is True
    assert records["SP-015A"]["pr"] == 36
    assert records["SP-015A"]["approved_head"] == (
        "1fdfc001defca37dc517efe0db2e623568d0740a"
    )
    assert records["SP-015A"]["merge_commit"] == (
        "712b6f6e3d233d008d22098bec4a8f317af603c3"
    )
    assert records["SP-015A"]["merged_at"] == "2026-07-20T14:10:27Z"
    assert records["SP-015A"]["main_quality_gate"] == "PASSED"
    assert records["SP-015R"]["status"] == sp015r_status
    assert records["SP-015R"]["base_commit"] == (
        "712b6f6e3d233d008d22098bec4a8f317af603c3"
    )
    assert records["SP-015R"]["branch"] == (
        "docs/sp-015r-release-authorization-readiness"
    )
    assert records["SP-015R"]["pr"] == 37
    assert records["SP-015R"]["approved_head"] == (
        "12df0d34ea62271910bbfdc85d4e04e64719b24c"
    )
    assert records["SP-015R"]["merge_commit"] == (
        "22f88d1da962fb436c48c19e5343fad8bf62f5f6"
    )
    assert records["SP-015R"]["merged_at"] == "2026-07-21T18:09:03Z"
    assert records["SP-015R"]["main_quality_gate"] == "PASSED"
    assert records["SP-015R"]["main_quality_gate_run"] == 29855987444
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert records["SP-016"]["name"] == sp016_name
    assert records["SP-016"]["status"] == sp016_status
    assert records["SP-016"]["planning_baseline_defined"] is True
    assert records["SP-016"]["approved"] is True
    assert records["SP-016"]["implementation_started"] is True
    assert records["SP-016"]["implementation_complete"] is True
    assert records["SP-016"]["manual_acceptance_status"] == "PASSED"
    assert records["SP-016"]["completed"] is True
    assert records["SP-016"]["archived"] is True
    assert records["SP-016"]["rfc"] == "RFC-025"
    assert records["SP-016"]["adrs"] == ["ADR-054", "ADR-055"]
    assert records["SP-016"]["base_commit"] == (
        "2b4f312b6b2bae388ae9819f66fcf2f00dc4dbf4"
    )
    assert records["SP-016"]["feature_pr"] == 40
    assert records["SP-016"]["approved_head"] == (
        "0e9fd454b11f6e8d01b256893bed98c3a07ff854"
    )
    assert records["SP-016"]["merge_commit"] == (
        "bc1bac632920c5c07823cd34c5f908086d4d923d"
    )
    assert records["SP-016"]["merged_at"] == "2026-07-22T14:51:34Z"
    assert records["SP-016"]["acceptance"] == "ACC-016 PASSED / FINAL"
    acceptance = state["acceptance_records"]["ACC-016"]
    assert acceptance["status"] == "PASSED / FINAL"
    assert acceptance["baseline_commit"] == (
        "bc1bac632920c5c07823cd34c5f908086d4d923d"
    )
    assert acceptance["manual_acceptance"] is True
    assert acceptance["scenarios"] == {letter: "PASSED" for letter in "ABCDEFGHIJ"}
    assert state["module_status"]["Waiting_For"] == (
        "Integrated / Verified / Manual acceptance passed"
    )
    assert "ARCHIVED" in records["SP-017"]["status"]

    documents = {
        "status": ROOT / "docs/project/PROJECT_STATUS.md",
        "roadmap": ROOT / "docs/project/ROADMAP.md",
        "brain": ROOT / "docs/project/PROJECT_BRAIN.md",
        "health": ROOT / "docs/project/PROJECT_HEALTH.md",
        "version_matrix": ROOT / "docs/project/VERSION_MATRIX.md",
        "release_checklist": ROOT / "docs/project/RELEASE_CHECKLIST.md",
        "release_notes": ROOT / "docs/releases/v0.34.0-alpha.md",
        "readme": ROOT / "README.md",
        "changelog": ROOT / "CHANGELOG.md",
    }
    text = {
        name: path.read_text(encoding="utf-8-sig") for name, path in documents.items()
    }

    assert f"| SP-015A | {sp015a_status} |" in text["status"]
    assert f"| SP-015R | {sp015r_status} |" in text["status"]
    assert f"| SP-016 | {sp016_status} |" in text["status"]
    assert f"| SP-016 | {sp016_name} | COMPLETED / ARCHIVED |" in text["roadmap"]
    assert "> 当前治理任务：None" in text["brain"]
    assert f"> SP-015A 状态：{sp015a_status}" in text["brain"]
    assert f"> SP-015R 状态：{sp015r_status}" in text["brain"]
    assert "最近完成的 Product SP：SP-021" in text["brain"]
    assert "当前 Product SP：None" in text["brain"]
    assert "ACC-016 状态：PASSED / FINAL" in text["brain"]
    assert "ACC-017 状态：PASSED / FINAL" in text["brain"]
    assert "Current governance task | None" in text["health"]
    assert "Alpha / PRE_RELEASE_PUBLISHED" in text["health"]
    assert "**治理状态：** REL-035 / FINAL_RECONCILED / ARCHIVED" in text["version_matrix"]
    assert (
        "SP-015、SP-015A 与 SP-015R 已封存；SP-016 当时仍仅为候选"
        in text["release_checklist"]
    )
    stale_governance_markers = (
        "SP-015A Status: IN_PROGRESS / DRAFT_PR_OPEN",
        "SP-015A / IN_PROGRESS / DRAFT_PR_OPEN",
        "| SP-015A | IN_PROGRESS / DRAFT_PR_OPEN |",
        "SP-015R Status: IN_PROGRESS / DRAFT_PR_OPEN",
        "SP-015R / IN_PROGRESS / DRAFT_PR_OPEN",
        "| SP-015R | IN_PROGRESS / DRAFT_PR_OPEN |",
        "SP-015R merge, its main Quality Gate",
        "SP-015R merged and its main Quality Gate passes\n- [ ]",
    )
    assert all(
        marker not in content
        for marker in stale_governance_markers
        for content in text.values()
    )
    stale_candidate = "SP-016 " + "Notification" + " Delivery"
    assert all(stale_candidate not in content for content in text.values())
    realtime_mirror_fields = (
        "tag_created",
        "tag_name",
        "github_release_created",
        "github_release_url",
        "release_blocked_by",
    )
    assert all(
        field not in content
        for field in realtime_mirror_fields
        for content in text.values()
    )
    assert (
        "外部发布验证以 GitHub Tag 与 GitHub Release 为权威来源。"
    ) in text["release_checklist"]
    assert "最终发布提交已准备" in text["release_checklist"]
    assert "- [ ] SP-015R merged" not in text["release_checklist"]
    assert "上一已发布版本为 `v0.34.0`" in text["readme"]
    assert "Pre-release" in text["readme"]
    assert "GitHub Tags and GitHub Releases" in text["readme"]
    assert "上一已发布 Tag：`v0.34.0`" in text["status"]
    assert "目标类型为 Pre-release" in text["status"]
    assert "GitHub Tags and GitHub Releases" in text["status"]
    assert "Authorized Tag：`v0.34.0`" in text["release_notes"]
    assert "GitHub Release Type：Pre-release" in text["release_notes"]
    assert "GitHub Tags and GitHub Releases" in text["release_notes"]
    transient_publication_markers = (
        "publication pending",
        "pending final release operation",
        "pending the final external release operation",
    )
    assert all(
        marker.lower() not in content.lower()
        for marker in transient_publication_markers
        for content in text.values()
    )


def test_sp016_adopted_artifacts_debt_and_current_documents_are_consistent() -> None:
    state = _load_state()
    rfc = (ROOT / "docs/rfc/025-canonical-waiting-for-domain.md").read_text(
        encoding="utf-8-sig"
    )
    adr = (ROOT / "docs/adr/ADR-054-canonical-waiting-for-domain.md").read_text(
        encoding="utf-8-sig"
    )
    agenda_adr = (
        ROOT / "docs/adr/ADR-055-daily-agenda-optional-source-composition.md"
    ).read_text(encoding="utf-8-sig")
    architecture = (
        ROOT / "docs/architecture/WAITING_FOR_DOMAIN.md"
    ).read_text(encoding="utf-8-sig")
    acceptance = (
        ROOT / "docs/acceptance/SP-016-waiting-for-domain.md"
    ).read_text(encoding="utf-8-sig")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8-sig")

    assert "Status: Adopted" in rfc
    assert "Status: Accepted" in adr
    assert "Status: Accepted" in agenda_adr
    assert "followups.db" in architecture
    assert "状态：PASSED / FINAL" in acceptance
    assert "结果：10 / 10 场景通过" in acceptance
    assert "H 保持 `AUTOMATED_VERIFICATION_PASSED`" in acceptance
    assert "I 保持 `AUTOMATED_VERIFICATION_PASSED`" in acceptance
    assert "J 保持 `AUTOMATED_VERIFICATION_PASSED`" in acceptance
    roadmap_rows = (
        "| SP-016 | Canonical Waiting-For Domain & Agenda Closure |",
        "| SP-017 | 跟进交互与捕获闭环——",
        "| SP-018 | Work Log Query Boundary & Context Closure |",
        "| SP-019 | Daily Review Read Model & Deterministic Follow-up View |",
    )
    positions = [roadmap.index(row) for row in roadmap_rows]
    assert positions == sorted(positions)
    assert (
        "| SP-017 | 跟进交互与捕获闭环——确定性 Waiting-For 交互、"
        "Inbox 捕获确认和持久化 Inbox-to-Waiting-For 转换 | "
        "COMPLETED / ARCHIVED |"
    ) in roadmap

    open_debt = state["open_technical_debt"]
    resolved_debt = state["resolved_technical_debt"]
    assert all(not entry.startswith("CI-002:") for entry in open_debt)
    assert all(not entry.startswith("AGENDA-001:") for entry in open_debt)
    assert any(
        entry["id"] == "CI-002" and entry["status"] == "RESOLVED"
        for entry in resolved_debt
    )
    assert any(
        entry["id"] == "AGENDA-001" and entry["status"] == "RESOLVED"
        for entry in resolved_debt
    )

    current_documents = (
        ROOT / "ARCHITECTURE.md",
        ROOT / "docs/project/KNOWN_LIMITATIONS.md",
        ROOT / "docs/project/TECHNICAL_DEBT.md",
        ROOT / "docs/project/ROADMAP.md",
        ROOT / "docs/project/PROJECT_STATUS.md",
        ROOT / "docs/project/PROJECT_HEALTH.md",
        ROOT / "docs/project/PROJECT_BRAIN.md",
        ROOT / "docs/review/CURRENT_RISKS.md",
    )
    stale_markers = (
        "v0.34.0 Alpha Candidate",
        "current main: 574442",
        "当前版本：0.33.0",
        "project_state.json 是唯一机器可读实时 main 状态源",
    )
    for document in current_documents:
        content = document.read_text(encoding="utf-8-sig")
        assert all(marker.lower() not in content.lower() for marker in stale_markers)


def test_release_authorization_is_stable_and_github_is_authoritative() -> None:
    state = _load_state()
    release = state["release_status"]
    release_notes = (ROOT / "docs/releases/v0.34.0-alpha.md").read_text(
        encoding="utf-8-sig"
    )

    assert release == {
        "current_version": "0.35.0",
        "release_stage": "alpha",
        "release_authorization": "AUTHORIZED / PUBLISHED",
        "publication_status": "PRE_RELEASE_PUBLISHED",
        "publication_authority": "GitHub Tags and GitHub Releases",
        "published_tag": "v0.35.0",
        "previous_published_tag": "v0.34.0",
        "github_release_type": "prerelease",
        "maturity": "Alpha / local-first / single-user-oriented",
        "binary_assets": "none",
        "published_releases": {
            "v0.35.0": {
                "name": "v0.35.0 Alpha — Local Daily Operating Loop",
                "status": "PRE_RELEASE_PUBLISHED / REMOTE_VERIFIED",
                "release_type": "prerelease",
                "binary_assets": 0,
                "draft": False,
                "tag": "v0.35.0",
                "tag_object_sha": "99de47895b967bc41c3b1dcb3d2caaa630fcd4de",
                "tag_peeled_commit": (
                    "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503"
                ),
                "tag_authorized": True,
                "tag_created": True,
                "github_release_authorized": True,
                "github_release_published": True,
                "github_release_id": 363770731,
                "github_release_published_at": "2026-08-02T11:32:43Z",
                "github_release_url": (
                    "https://github.com/y19870785/ai-lab-os/releases/tag/v0.35.0"
                ),
            }
        },
    }
    realtime_mirrors = {
        "tag_created",
        "tag_name",
        "github_release_created",
        "github_release_url",
        "release_blocked_by",
    }
    assert realtime_mirrors.isdisjoint(release)
    assert "Alpha / local-first / single-user-oriented" in release_notes
    assert "Authorized Tag：`v0.34.0`" in release_notes
    assert "GitHub Release Type：Pre-release" in release_notes
    assert "GitHub Tags and GitHub Releases" in release_notes


def test_governance_source_responsibilities_are_explicit() -> None:
    state = _load_state()
    sources = state["governance_sources"]

    assert sources["machine_readable_project_state"] == "project_state.json"
    assert sources["runtime_product_version"] == "pyproject.toml:[project].version"
    assert {"readme", "project_brain", "roadmap", "changelog_and_release_notes"} <= set(
        sources
    )


def test_readme_has_no_stale_phase_or_manual_document_counts() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")

    assert "Phase 4" not in readme
    assert "v0.22.0" not in readme
    assert re.search(r"\b\d+\s+(RFC|ADR)s?\b", readme, flags=re.IGNORECASE) is None


def test_sp016_closure_contains_no_local_or_transient_governance_state() -> None:
    state = _load_state()
    paths = (
        STATE_PATH,
        ROOT / "docs/acceptance/SP-016-waiting-for-domain.md",
        ROOT / "docs/project/PROJECT_STATUS.md",
        ROOT / "docs/project/PROJECT_HEALTH.md",
        ROOT / "docs/project/PROJECT_BRAIN.md",
        ROOT / "docs/project/ROADMAP.md",
    )
    content = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths)

    assert "next_action" not in state
    assert "C:\\Users\\" not in content
    assert "AppData\\Local\\Temp" not in content
    assert "ai-lab-acc016-" not in content
    sp016 = state["sp_records"]["SP-016"]
    transient_fields = {
        "closure_pr",
        "closure_head",
        "closure_merge_commit",
        "draft_pr",
        "github_check_status",
    }
    assert transient_fields.isdisjoint(sp016)


def test_sp017_is_accepted_reconciled_and_archived() -> None:
    state = _load_state()
    records = state["sp_records"]
    sp017 = records["SP-017"]
    expected_status = (
        "APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / "
        "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
    )

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert state["current_work"] is None
    assert "next_action" not in state

    assert sp017 == {
        "name": "Follow-up Interaction & Capture Closure",
        "status": expected_status,
        "planning_baseline_defined": True,
        "approved": True,
        "implementation_started": True,
        "implementation_complete": True,
        "base_commit": "c1ef6fc5d2c46896748643dae08554725ce16f43",
        "branch": "feat/sp-017-follow-up-interaction-closure",
        "planning_pr": 42,
        "planning_head": "72a5976e3a93879c46800413f48367ee54391879",
        "planning_merge_commit": "c1ef6fc5d2c46896748643dae08554725ce16f43",
        "feature_pr": 43,
        "approved_head": "40319102eb7aaea90a24d8abdf106e406b680618",
        "feature_merge_commit": "32bb9c0a939c65f2278fc2b6be8d072fb2e3656a",
        "merged_at": "2026-07-23T12:25:57Z",
        "review": "APPROVED",
        "post_merge_acceptance": "PASSED",
        "acceptance": "ACC-017 A-O PASSED / FINAL",
        "main_quality_gate": "PASSED",
        "main_quality_gate_run": 30006958413,
        "target_version": "0.35.0",
        "rfc": "RFC-026",
        "adrs": ["ADR-056", "ADR-057"],
        "scope": (
            "Deterministic Waiting-For interaction, Inbox capture confirmation, "
            "durable Inbox-to-Waiting-For conversion and explicit lifecycle commands"
        ),
    }
    assert {"pr", "head", "draft_pr", "github_check_status"}.isdisjoint(sp017)

    acc017 = state["acceptance_records"]["ACC-017"]
    assert acc017["status"] == "PASSED / FINAL"
    assert acc017["baseline_commit"] == (
        "32bb9c0a939c65f2278fc2b6be8d072fb2e3656a"
    )
    assert acc017["manual_acceptance"] is True
    assert acc017["scenarios"] == {
        letter: "PASSED" for letter in "ABCDEFGHIJKLMNO"
    }
    assert records["SP-019"]["approved"] is True
    assert records["SP-019"]["implementation_started"] is True

    rfc = (
        ROOT / "docs/rfc/026-follow-up-interaction-capture-closure.md"
    ).read_text(encoding="utf-8-sig")
    adr056 = (
        ROOT / "docs/adr/ADR-056-deterministic-follow-up-interaction-boundary.md"
    ).read_text(encoding="utf-8-sig")
    adr057 = (
        ROOT / "docs/adr/ADR-057-inbox-to-waiting-for-resolution-saga.md"
    ).read_text(encoding="utf-8-sig")
    decision_index = (
        ROOT / "docs/project/DECISION_INDEX.md"
    ).read_text(encoding="utf-8-sig")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8-sig")
    acceptance = (
        ROOT / "docs/acceptance/SP-017-follow-up-interaction-closure.md"
    ).read_text(encoding="utf-8-sig")

    assert "Status: Adopted" in rfc
    assert "Status: Accepted" in adr056
    assert "Status: Accepted" in adr057
    assert (
        "| RFC-026 | Follow-up Interaction and Capture Closure | "
        "Adopted |"
    ) in decision_index
    assert (
        "| ADR-056 | Deterministic Follow-up Interaction Boundary | Accepted |"
    ) in decision_index
    assert (
        "| ADR-057 | Inbox-to-Waiting-For Resolution Saga | Accepted |"
    ) in decision_index
    assert "SP-016 人工验收待执行" not in decision_index
    assert (
        "LOCAL_AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / "
        "PR_QUALITY_GATE_PASSED / POST_MERGE_QUALITY_GATE_PASSED / "
        "INDEPENDENT_REVIEW_APPROVED / FINAL"
    ) in acceptance
    assert "Feature PR：#43" in acceptance
    assert "Approved Head：`40319102eb7aaea90a24d8abdf106e406b680618`" in acceptance
    assert (
        "Feature Merge Commit：`32bb9c0a939c65f2278fc2b6be8d072fb2e3656a`"
        in acceptance
    )
    assert "PR Quality Gate Run：`30006130019`" in acceptance
    assert "Post-Merge main Quality Gate Run：`30006958413`" in acceptance
    assert "Independent Review：`APPROVED`" in acceptance
    assert "ACC-017 A～O：PASSED / FINAL" in acceptance
    assert "INVALID_ACCEPTANCE_HARNESS" in acceptance
    assert all(f"ACC-017-{letter}" in acceptance for letter in "ABCDEFGHIJKLMNO")

    ordered_rows = (
        "| SP-017 | 跟进交互与捕获闭环——",
        "| SP-018 | Work Log Query Boundary & Context Closure |",
        "| SP-019 | Daily Review Read Model & Deterministic Follow-up View |",
    )
    positions = [roadmap.index(row) for row in ordered_rows]
    assert positions == sorted(positions)

    current_documents = (
        ROOT / "README.md",
        ROOT / "ARCHITECTURE.md",
        ROOT / "docs/rfc/026-follow-up-interaction-capture-closure.md",
        ROOT / "docs/project/PROJECT_STATUS.md",
        ROOT / "docs/project/PROJECT_HEALTH.md",
        ROOT / "docs/project/PROJECT_BRAIN.md",
        ROOT / "docs/project/ROADMAP.md",
    )
    current_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in current_documents
    )
    required_markers = (
        "SP-017 状态：APPROVED / MERGED / ACCEPTED / RECONCILED / ARCHIVED",
            "当前 Product SP：None",
        "RFC-026 Adopted",
        "ACC-017 状态：PASSED / FINAL",
        (
            "| SP-018 | Work Log Query Boundary & Context Closure | "
            "COMPLETED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED |"
        ),
            (
                "| SP-019 | Daily Review Read Model & Deterministic Follow-up View | "
                "APPROVED / MERGED / POST_MERGE_VERIFIED / "
                "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |"
            ),
    )
    assert all(marker in current_text for marker in required_markers)
    forbidden_markers = (
        "APPROVED_FOR_IMPLEMENTATION / IN_PROGRESS",
        "INDEPENDENT_REVIEW_CHANGES_REQUESTED",
        "GITHUB_QUALITY_GATE_PENDING",
        "SP-017 implementation in progress",
    )
    assert all(marker not in current_text for marker in forbidden_markers)

    transient_fields = {
        "draft_pr",
        "github_check_status",
    }
    assert transient_fields.isdisjoint(sp017)


def test_sp018_is_merged_accepted_verified_and_archived() -> None:
    state = _load_state()
    records = state["sp_records"]
    sp018 = records["SP-018"]
    acc018 = state["acceptance_records"]["ACC-018"]

    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["current_work"] is None
    assert "next_action" not in state

    assert sp018["name"] == "Work Log Query Boundary & Context Closure"
    assert sp018["status"] == (
        "APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / "
        "MANUAL_ACCEPTANCE_PASSED / POST_MERGE_VERIFIED / "
        "RECONCILED / ARCHIVED"
    )
    assert sp018["planning_baseline_defined"] is True
    assert sp018["approved"] is True
    assert sp018["implementation_started"] is True
    assert sp018["implementation_complete"] is True
    assert sp018["manual_acceptance_status"] == "PASSED"
    assert sp018["completed"] is True
    assert sp018["reconciled"] is True
    assert sp018["archived"] is True
    assert sp018["planning_pr"] == 45
    assert sp018["planning_head"] == "e485c99d9734a43665c0c891e886e91b59c577d6"
    assert sp018["planning_merge_commit"] == (
        "ee06f6a20004bdbf24fc94c8420c18cf1a3d45b3"
    )
    assert sp018["feature_pr"] == 46
    assert sp018["approved_head"] == (
        "e941cadc783a6ac8a4bd3c75b55adf77e0a651a3"
    )
    assert sp018["feature_merge_commit"] == (
        "83ecb557fedd1d898712afc59ad13b3e0a684413"
    )
    assert sp018["merged_at"] == "2026-07-26T09:35:04Z"
    assert sp018["reconciliation_pr"] == 47
    assert sp018["reconciliation_merge_commit"] == (
        "4e0d730a8bfdefa6277c7526a028e7247d7ddc43"
    )
    assert sp018["reconciled_at"] == "2026-07-26T10:32:07Z"
    assert sp018["post_reconciliation_quality_gate_run"] == 30198434517
    assert sp018["review"] == "APPROVED"
    assert sp018["acceptance"] == "ACC-018 A-O PASSED / FINAL"
    assert sp018["post_merge_acceptance"] == "PASSED"
    assert sp018["main_quality_gate"] == "PASSED"
    assert sp018["main_quality_gate_run"] == 30196719409
    assert sp018["target_version"] == "0.35.0"
    assert sp018["rfc"] == "RFC-027"
    assert sp018["adrs"] == ["ADR-058", "ADR-059", "ADR-060"]
    assert {
        "draft_pr",
        "github_check_status",
        "merge_commit",
        "merged",
        "accepted",
    }.isdisjoint(sp018)

    assert acc018["status"] == "PASSED / FINAL"
    assert acc018["manual_acceptance"] is True
    assert acc018["acceptance_head"] == (
        "e941cadc783a6ac8a4bd3c75b55adf77e0a651a3"
    )
    assert acc018["post_merge_verified_commit"] == (
        "83ecb557fedd1d898712afc59ad13b3e0a684413"
    )
    assert acc018["post_merge_quality_gate_run"] == 30196719409
    assert acc018["scenarios"] == {
        letter: "PASSED" for letter in "ABCDEFGHIJKLMNO"
    }
    notes = "\n".join(acc018["notes"])
    assert "41ffcba093f149e31dee06c987a5305c651c349a" in notes
    assert "e941cadc783a6ac8a4bd3c75b55adf77e0a651a3" in notes
    assert "30196719409" in notes
    assert "without query or list fallback" in notes
    assert "no real Provider calls" in notes
    assert "INVALID_ACCEPTANCE_HARNESS" in notes

    rfc = (
        ROOT / "docs/rfc/027-work-log-query-boundary-context-closure.md"
    ).read_text(encoding="utf-8-sig")
    adr058 = (
        ROOT / "docs/adr/ADR-058-work-log-service-over-episodic-storage.md"
    ).read_text(encoding="utf-8-sig")
    adr059 = (
        ROOT / "docs/adr/ADR-059-canonical-work-log-id-and-legacy-projection.md"
    ).read_text(encoding="utf-8-sig")
    adr060 = (
        ROOT / "docs/adr/ADR-060-explicit-work-log-context-references.md"
    ).read_text(encoding="utf-8-sig")
    acceptance = (
        ROOT / "docs/acceptance/SP-018-work-log-query-boundary-context-closure.md"
    ).read_text(encoding="utf-8-sig")
    decision_index = (
        ROOT / "docs/project/DECISION_INDEX.md"
    ).read_text(encoding="utf-8-sig")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8-sig")
    brain = (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(
        encoding="utf-8-sig"
    )

    assert "Status: Adopted" in rfc
    assert "ACC-018 A～O" in rfc
    assert "30196719409" in rfc
    assert all(
        "Status: Accepted" in content for content in (adr058, adr059, adr060)
    )
    assert (
        "LOCAL_AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / "
        "PR_QUALITY_GATE_PASSED / POST_MERGE_QUALITY_GATE_PASSED / "
        "INDEPENDENT_REVIEW_APPROVED / FINAL"
    ) in acceptance
    assert all(f"ACC-018-{letter}" in acceptance for letter in "ABCDEFGHIJKLMNO")
    assert acceptance.count("状态：PASSED") == 15
    assert "功能 PR：#46" in acceptance
    assert (
        "批准 Head：`e941cadc783a6ac8a4bd3c75b55adf77e0a651a3`"
        in acceptance
    )
    assert (
        "功能合并 Commit：`83ecb557fedd1d898712afc59ad13b3e0a684413`"
        in acceptance
    )
    assert "SP-018A 对账 PR：#47（MERGED）" in acceptance
    assert "4e0d730a8bfdefa6277c7526a028e7247d7ddc43" in acceptance
    assert "30198434517" in acceptance
    assert "PR Quality Gate Run：`30195401115`" in acceptance
    assert "合并后 main Quality Gate Run：`30196719409`" in acceptance
    assert "独立审查：`APPROVED`" in acceptance
    assert "ACC-018 A～O：PASSED / FINAL" in acceptance
    assert "INVALID_ACCEPTANCE_HARNESS" in acceptance
    assert (
        "| RFC-027 | Work Log Query Boundary and Context Closure | "
        "Adopted |"
    ) in decision_index
    assert all(
        f"| ADR-{number} |" in decision_index for number in ("058", "059", "060")
    )
    assert (
        "| SP-018 | Work Log Query Boundary & Context Closure | "
        "COMPLETED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED |"
    ) in roadmap
    assert (
        "| SP-019 | Daily Review Read Model & Deterministic Follow-up View | "
        "APPROVED / MERGED / POST_MERGE_VERIFIED / "
        "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |"
    ) in roadmap
    assert "SP-018 永久产品事实" in brain
    assert "不会创建 `work_logs.db`" in brain
    assert (
        "SP-019 Planning Baseline 已通过独立审查并由 PR #48 Squash Merge"
        in brain
    )
    assert "旧工作日志投影表" in rfc
    assert "普通随机 Memory ID 仍不作为公开 alias" in rfc
    assert "历史 `inbox_wl_<合法历史格式>` 是唯一受限兼容 lookup alias" in rfc
    assert "返回同一对象的 canonical `wl_legacy_" in rfc
    assert "SP-018 没有业务结果 candidate cap" in rfc
    assert "这些阈值只产生观测信号" in rfc
    assert "普通随机 Memory ID" in adr059
    assert "唯一受限兼容 Alias" in adr059
    acc_d = acceptance.split("## ACC-018-D", maxsplit=1)[1].split(
        "## ACC-018-E", maxsplit=1
    )[0]
    acc_f = acceptance.split("## ACC-018-F", maxsplit=1)[1].split(
        "## ACC-018-G", maxsplit=1
    )[0]
    acc_g = acceptance.split("## ACC-018-G", maxsplit=1)[1].split(
        "## ACC-018-H", maxsplit=1
    )[0]
    acc_l = acceptance.split("## ACC-018-L", maxsplit=1)[1].split(
        "## ACC-018-M", maxsplit=1
    )[0]
    assert "WorkLogService 接受合法历史 `inbox_wl_...` alias" in acc_d
    assert "数据量超过 slow-query/scanned-row observability warning threshold" in acc_f
    assert "历史 Inbox row 投影为稳定 `wl_legacy_...`" in acc_g
    assert "API、CLI、CEO Assistant、Agenda 与 Brief" in acc_l
    assert "状态：PASSED" in acceptance

    governance_files = (
        rfc,
        adr058,
        adr059,
        adr060,
        acceptance,
        decision_index,
        roadmap,
        brain,
    )
    stale_state_markers = (
        "SP-018 Draft implementation facts",
        "MANUAL_ACCEPTANCE_NOT_EXECUTED",
        "SP-018 / NOT_MERGED",
        "ACC-018 人工验收尚未执行",
        "状态：IMPLEMENTATION_DRAFT / NOT_EXECUTED",
    )
    assert all(
        marker not in content
        for marker in stale_state_markers
        for content in governance_files
    )


def test_sp018_product_entrypoints_use_the_canonical_work_log_boundary() -> None:
    """Keep Work Log product paths from drifting back to generic Memory access."""

    paths = {
        "assistant": ROOT / "applications/ceo_assistant/application.py",
        "inbox": ROOT / "core/inbox/service.py",
        "agenda": ROOT / "core/agenda/service.py",
        "api": ROOT / "api/routes/work_logs.py",
        "cli": ROOT / "cli/commands/work_log_cmd.py",
        "legacy_cli": ROOT / "cli/commands/log_cmd.py",
        "cli_runtime": ROOT / "cli/runtime.py",
    }
    text = {
        name: path.read_text(encoding="utf-8-sig")
        for name, path in paths.items()
    }
    assert "self._work_logs.create_from_input(" in text["assistant"]
    assert "self._work_logs.query_from_input(" in text["assistant"]
    assert "self._work_logs.get(" in text["assistant"]
    assert "self._work_logs.create_from_inbox(" in text["inbox"]
    assert "self._work_logs.list(" in text["agenda"]
    assert '_service(system, request, "create").create_from_input(' in text["api"]
    assert '_service(system, request, "list").query_from_input(' in text["api"]
    assert "execute_work_log_operation" in text["cli"]
    assert "execute_work_log_operation" in text["legacy_cli"]
    assert "service.create_from_input(" in text["cli_runtime"]
    assert "service.query_from_input(" in text["cli_runtime"]
    assert "WorkLogCreateCommand(" not in text["api"]
    assert "WorkLogQuery(" not in text["api"]
    assert "WorkLogCreateCommand(" not in text["cli"]
    assert "WorkLogQuery(" not in text["cli"]
    assert "MemoryManager" not in "\n".join(
        text[name] for name in ("api", "cli", "legacy_cli")
    )

    assistant_write = text["assistant"].split(
        "async def _handle_work_log(", maxsplit=1
    )[1].split("async def _extract_work_entities(", maxsplit=1)[0]
    inbox_write = text["inbox"].split(
        "async def resolve_to_work_log(", maxsplit=1
    )[1].split("async def resolve_to_waiting_for(", maxsplit=1)[0]
    agenda_read = text["agenda"].split(
        "async def _wl(", maxsplit=1
    )[1].split("def _sort_key(", maxsplit=1)[0]
    assert "save_memory" not in assistant_write
    assert "save_memory" not in inbox_write
    assert "retrieve_memory" not in agenda_read


def test_sp019_daily_review_is_merged_verified_reconciled_and_archived() -> None:
    state = _load_state()
    sp019 = state["sp_records"]["SP-019"]
    acc019 = state["acceptance_records"]["ACC-019"]

    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert state["current_work"] is None
    assert state["release_status"]["previous_published_tag"] == "v0.34.0"
    assert state["release_status"]["current_version"] == "0.35.0"
    assert "SP-020" in state["sp_records"]
    assert sp019 == {
        "name": "Daily Review Read Model & Deterministic Follow-up View",
        "status": (
            "APPROVED / MERGED / POST_MERGE_VERIFIED / "
            "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
        ),
        "planning_baseline_defined": True,
        "planning_baseline_approved": True,
        "approved": True,
        "implementation_started": True,
        "implementation_complete": True,
        "completed": True,
        "reconciled": True,
        "archived": True,
        "implementation_base": "410ded0533943d23c622fa6788f37a3c06e99ad1",
        "phase_0_status": (
            "APPROVED / MERGED / POST_MERGE_VERIFIED / ACCEPTED"
        ),
        "phase_0_pr": 50,
        "phase_0_approved_head": (
            "9dff57f34e26106cb72da9ecf92ab8e208347e07"
        ),
        "phase_0_merge_commit": (
            "410ded0533943d23c622fa6788f37a3c06e99ad1"
        ),
        "phase_0_merged_at": "2026-07-26T17:04:49Z",
        "phase_0_post_merge_quality_gate_run": 30211823590,
        "daily_review_status": "MERGED / POST_MERGE_VERIFIED / ACCEPTED",
        "approved_implementation_head": (
            "1f2975503cd79047137a4a9f47096668fd4341c5"
        ),
        "feature_pr": 51,
        "acceptance_evidence_head": (
            "420da28664914fda8ccbecadf90947380ec43473"
        ),
        "feature_merge_commit": (
            "a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49"
        ),
        "merged_at": "2026-07-28T17:18:41Z",
        "main_quality_gate": "PASSED",
        "main_quality_gate_run": 30382312419,
        "post_merge_verification": "PASSED",
        "reconciliation_pr": 52,
        "base_commit": "4e0d730a8bfdefa6277c7526a028e7247d7ddc43",
        "branch": "feat/sp-019-daily-review-read-model",
        "planning_pr": 48,
        "planning_head": "282dd939ff264b0f23d5070b6f632aa0442531ea",
        "planning_merge_commit": "e7fc5b1dd66ff7828c1697bfd5610f300599eee5",
        "planning_merged_at": "2026-07-26T14:19:41Z",
        "post_planning_quality_gate_run": 30205853257,
        "planning_reconciliation_pr": 49,
        "target_version": "0.35.0",
        "rfc": "RFC-028",
        "adrs": ["ADR-061", "ADR-062"],
        "acceptance": "ACC-019 PASSED / FINAL",
        "user_task_workspace_prerequisite": "ACCEPTED",
        "scope": (
            "On-demand non-persistent Daily Review read model and "
            "deterministic follow-up view"
        ),
    }
    assert acc019["status"] == "PASSED / FINAL"
    assert acc019["manual_acceptance"] is True
    assert acc019["approved_implementation_head"] == (
        "1f2975503cd79047137a4a9f47096668fd4341c5"
    )
    assert acc019["acceptance_evidence_head"] == (
        "420da28664914fda8ccbecadf90947380ec43473"
    )
    assert acc019["post_merge_verified_commit"] == (
        "a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49"
    )
    assert acc019["post_merge_quality_gate_run"] == 30382312419
    assert acc019["python_version"] == "3.12.10"
    assert acc019["driver_hash"] == (
        "7b5f2905c59cdd8ca47213042fe83d7785759e21935f82ffd04edae62e7f20f4"
    )
    assert acc019["provider_calls"] == 0
    assert acc019["harness_incidents"] == 3
    assert acc019["scenarios"] == {
        letter: "PASSED" for letter in "ABCDEFGHIJKLM"
    }
    notes = "\n".join(acc019["notes"])
    assert "Three discarded runs" in notes
    assert "without product changes" in notes
    assert (
        "SP-019 was Squash merged as "
        "a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49, passed main "
        "Quality Gate 30382312419, and was archived without version, tag or "
        "release changes."
    ) in notes
    assert sp019["completed"] is True
    assert sp019["archived"] is True
    assert {
        "merge_commit",
        "reconciliation_merge_commit",
        "reconciled_at",
        "post_reconciliation_quality_gate_run",
    }.isdisjoint(sp019)

    rfc = (
        ROOT / "docs/rfc/028-daily-review-read-model-deterministic-follow-up.md"
    ).read_text(encoding="utf-8-sig")
    adr061 = (
        ROOT / "docs/adr/ADR-061-daily-review-non-persistent-read-model.md"
    ).read_text(encoding="utf-8-sig")
    adr062 = (
        ROOT
        / "docs/adr/ADR-062-daily-review-source-failure-and-availability-semantics.md"
    ).read_text(encoding="utf-8-sig")
    acceptance = (
        ROOT / "docs/acceptance/SP-019-daily-review-read-model.md"
    ).read_text(encoding="utf-8-sig")
    decision_index = (
        ROOT / "docs/project/DECISION_INDEX.md"
    ).read_text(encoding="utf-8-sig")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(
        encoding="utf-8-sig"
    )
    brain = (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(
        encoding="utf-8-sig"
    )
    project_status = (ROOT / "docs/project/PROJECT_STATUS.md").read_text(
        encoding="utf-8-sig"
    )
    project_health = (ROOT / "docs/project/PROJECT_HEALTH.md").read_text(
        encoding="utf-8-sig"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")

    required_rfc_headings = (
        "## 1. 当前状态审计（Current State Audit）",
        "## 2. 用户问题（User Problem）",
        "## 3. Daily Agenda 边界（Daily Agenda Boundary）",
        "## 7. 日期与截至时点合同（Date and As-of Contract）",
        "## 8. 输出模型（Output Model）",
        "### 当前未闭环 Inbox（Current Pending Inbox）",
        "## 11. 排序与去重（Sorting and Deduplication）",
        "## 12. 数据源可用性（Source Availability）",
        "## 13. 失败语义（Failure Semantics）",
        "## 20. 实施阶段（Implementation Phases）",
        "## 21. 非目标（Non-goals）",
        "## 22. 风险（Risks）",
        "## 23. 停止条件（Stop Conditions）",
    )
    assert all(heading in rfc for heading in required_rfc_headings)
    assert "Status: Adopted" in rfc
    assert "UserTask Workspace Query Closure" in rfc
    assert "无需新 Schema、Migration" in rfc
    assert "`daily_review.source_failed`" in rfc
    assert "[as_of, as_of + 24 hours)" in rfc
    assert (
        "DailyReviewQuery\n"
        "- review_date: today | yesterday\n"
        "- limit: int = 50\n"
        "- offset: int = 0"
    ) in rfc
    assert (
        "合法范围保持为 `limit: 1..100`、`offset: >= 0`。默认值属于 "
        "`DailyReviewQuery` 合同本身；API 与 CEO Assistant 必须构造同一个默认 "
        "`DailyReviewQuery(review_date, limit=50, offset=0)`"
    ) in rfc
    assert (
        "查询验证必须先于任何 canonical source 读取。`limit=0`、"
        "`limit=101` 或 `offset=-1` 均返回 "
        "`daily_review.query_invalid + ErrorCategory.VALIDATION`，且不得访问"
        "任何 canonical source。"
    ) in rfc
    assert (
        "page\n"
        "- count\n"
        "- total_count\n"
        "- limit\n"
        "- offset\n"
        "- has_more"
    ) in rfc
    assert (
        "deterministic classification\n"
        "-> 按 (source_type, source_id) 去重并选定唯一 section\n"
        "-> 按全局稳定排序键排序\n"
        "-> 计算 total_count 与各 section_total_count\n"
        "-> 对全局结果应用 offset / limit\n"
        "-> 将当前 page items 按 section 分组"
    ) in rfc
    assert (
        "GET /daily-review?date=today&limit=50&offset=0"
    ) in rfc
    classification_contract = rfc.split(
        "## 9. 分类规则", maxsplit=1
    )[1].split("## 10. Follow-up 原因码", maxsplit=1)[0]
    assert "| Inbox pending at `as_of` |" not in classification_contract
    assert (
        "### 当前未闭环 Inbox（Current Pending Inbox）"
        in classification_contract
    )
    assert (
        "`pending_inbox` 是截至 `as_of` 的当前未闭环视图，不受 "
        "`review_date` 的 `[period_start, period_end)` 日期事实窗口过滤。"
    ) in classification_contract
    assert (
        "reason_code=inbox.pending\n"
        "section=pending_inbox\n"
        "effective_at=created_at\n"
        "predicate=status pending at as_of"
    ) in classification_contract
    assert (
        "同一个 Inbox item 只进入 `pending_inbox`，不得同时复制到 "
        "`follow_ups`，也不得作为 `review_date` 日期事实。"
    ) in classification_contract
    assert (
        "当前 pending Inbox items 必须计入全局 `total_count` 与 "
        "`pending_inbox.section_total_count`，并参与同一套全局分页。"
    ) in classification_contract
    source_status_contract = (
        rfc.split("## 12. 数据源可用性", maxsplit=1)[1]
        .split("## 13. 失败语义", maxsplit=1)[0]
        .split("```text", maxsplit=1)[1]
        .split("```", maxsplit=1)[0]
    )
    assert source_status_contract.strip().splitlines() == [
        "available",
        "disabled",
        "not_configured",
    ]
    assert "成功 payload 的 `source_status` 永远不包含 `failed`" in rfc
    assert (
        "| `daily_review.unavailable` | DISABLED | "
        "配置显式关闭 DailyReviewService |"
    ) in rfc
    assert (
        "| `daily_review.unavailable` | NOT_CONFIGURED | "
        "Composition Root 未组合所需 DailyReviewService |"
    ) in rfc
    failure_contract = rfc.split(
        "## 13. 失败语义", maxsplit=1
    )[1].split("## 14. Workspace 合同", maxsplit=1)[0]
    assert (
        "`limit=0`、`limit=101` 与 `offset=-1` 均返回 "
        "`daily_review.query_invalid + ErrorCategory.VALIDATION`；该失败路径"
        "不得读取任何 canonical source，也不得返回部分 `DailyReview` payload。"
    ) in failure_contract
    entry_contract = rfc.split(
        "## 15. 入口", maxsplit=1
    )[1].split("## 16. 存储决策", maxsplit=1)[0]
    assert (
        "GET /daily-review?date=today\n"
        "== GET /daily-review?date=today&limit=50&offset=0\n\n"
        "GET /daily-review?date=yesterday\n"
        "== GET /daily-review?date=yesterday&limit=50&offset=0"
    ) in entry_contract
    assert (
        "API 与 CEO Assistant 必须构造同一个默认 `DailyReviewQuery`，"
        "不得各自设置不同默认值"
    ) in entry_contract
    assert "Status: Accepted" in adr061
    assert "非持久化" in adr061
    assert "## 背景（Context）" in adr061
    assert "## 决策（Decision）" in adr061
    assert (
        "日期事实由 `review_date` 控制；当前未闭环视图，包括 "
        "`pending_inbox`，由 `as_of` 控制。"
    ) in adr061
    assert "Status: Accepted" in adr062
    assert "成功返回的 `DailyReview.source_status`" in adr062
    assert "不是成功 payload 的 `source_status` 值" in adr062
    assert "category=DISABLED" in adr062
    assert "category=NOT_CONFIGURED" in adr062
    assert "## 治理状态（Governance）" in adr062
    assert all(f"ACC-019-{letter}" in acceptance for letter in "ABCDEFGHIJKLM")
    for index, letter in enumerate("ABCDEFGHIJKLM"):
        next_letter = "ABCDEFGHIJKLM"[index + 1:index + 2]
        scenario = acceptance.split(
            f"## ACC-019-{letter}", maxsplit=1
        )[1]
        if next_letter:
            scenario = scenario.split(
                f"## ACC-019-{next_letter}", maxsplit=1
            )[0]
        else:
            scenario = scenario.split("## 正式验收证据", maxsplit=1)[0]
        assert scenario.rstrip().endswith("状态：PASSED")
    assert "ACC-019: PASSED / FINAL" in acceptance
    assert "manual_acceptance: true" in acceptance
    assert (
        "Approved Implementation Head: "
        "1f2975503cd79047137a4a9f47096668fd4341c5"
    ) in acceptance
    assert (
        "Driver SHA-256: "
        "7b5f2905c59cdd8ca47213042fe83d7785759e21935f82ffd04edae62e7f20f4"
    ) in acceptance
    assert "Provider calls 为 0" in acceptance
    assert "三次废弃运行" in acceptance
    assert (
        "Feature PR: #51\n"
        "Acceptance Evidence Head: "
        "420da28664914fda8ccbecadf90947380ec43473\n"
        "Feature Merge Commit: "
        "a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49\n"
        "Merged At: 2026-07-28T17:18:41Z\n"
        "Merge Method: SQUASH\n"
        "Main Quality Gate: 30382312419 / SUCCESS\n"
        "Ruff: SUCCESS\n"
        "pytest (non-real): SUCCESS"
    ) in acceptance
    planning_merge_contract = (
        "Planning PR：#48（MERGED）\n\n"
        "Approved Planning Head："
        "`282dd939ff264b0f23d5070b6f632aa0442531ea`\n\n"
        "Planning Merge Commit："
        "`e7fc5b1dd66ff7828c1697bfd5610f300599eee5`\n\n"
        "Planning Merged At：`2026-07-26T14:19:41Z`\n\n"
        "Post-Planning main Quality Gate：`30205853257`（SUCCESS）\n\n"
        "Independent Planning Review：APPROVED"
    )
    assert planning_merge_contract in acceptance
    assert "Planning PR：#48（OPEN / DRAFT / NOT MERGED）" not in acceptance
    acc_d = acceptance.split("## ACC-019-D", maxsplit=1)[1].split(
        "## ACC-019-E", maxsplit=1
    )[0]
    assert (
        "创建时间早于 review period、但在 `as_of` 时仍为 pending 的 "
        "Inbox item 必须出现在 `pending_inbox`"
    ) in acc_d
    acc_h = acceptance.split("## ACC-019-H", maxsplit=1)[1].split(
        "## ACC-019-I", maxsplit=1
    )[0]
    assert (
        "日期事实分类不得包含 Inbox pending；`inbox.pending` 是由 `as_of` "
        "控制的当前未闭环视图，不得作为 `review_date` 日期事实。"
    ) in acc_h
    acc_i = acceptance.split("## ACC-019-I", maxsplit=1)[1].split(
        "## ACC-019-J", maxsplit=1
    )[0]
    assert (
        "`inbox.pending` 必须由 Inbox item 在 `as_of` 的当前 pending 状态"
        "决定，不由 `review_date` 决定"
    ) in acc_i
    acc_j = acceptance.split("## ACC-019-J", maxsplit=1)[1].split(
        "## ACC-019-K", maxsplit=1
    )[0]
    assert (
        "同一个 Inbox item 只进入 `pending_inbox`，不得重复进入 `follow_ups`。"
    ) in acc_j
    acc_k = acceptance.split("## ACC-019-K", maxsplit=1)[1].split(
        "## ACC-019-L", maxsplit=1
    )[0]
    assert "DailyReviewQuery(review_date, limit=50, offset=0)" in acc_k
    assert (
        "省略 `limit/offset` 与显式 `limit=50/offset=0` 构造完全相同的 "
        "`DailyReviewQuery`"
    ) in acc_k
    assert (
        "`limit=0`、`limit=101`、`offset=-1` 返回 "
        "`daily_review.query_invalid + ErrorCategory.VALIDATION`，且不得访问"
        "任何 canonical source"
    ) in acc_k
    assert (
        "当前 pending Inbox items 计入全局 `total_count` 与 "
        "`pending_inbox.section_total_count`，并参与同一套全局分页"
    ) in acc_k
    assert "跨页顺序稳定，无重复、无遗漏" in acc_k
    assert "offset >= total_count" in acc_k
    assert "page.count=0" in acc_k
    acc_l = acceptance.split("## ACC-019-L", maxsplit=1)[1].split(
        "## ACC-019-M", maxsplit=1
    )[0]
    assert (
        "API 省略分页参数与显式 `limit=50/offset=0` 的结果一致"
        in acc_l
    )
    assert (
        "CEO Assistant 未提供结构化分页参数时必须使用同一个默认 "
        "`DailyReviewQuery(review_date, limit=50, offset=0)`；其默认第一页"
        "与 API 默认第一页必须返回相同当前 page 事实集合"
    ) in acc_l
    assert "GET /daily-review?date=today\n" in acc_l
    assert "date=today&limit=50&offset=0" in acc_l
    assert "## ACC-019-A — 基线与现有 Brief 替换" in acceptance
    assert "## ACC-019-K — 全局分页与截断" in acceptance
    assert "| RFC-028 |" in decision_index
    assert "| ADR-061 |" in decision_index
    assert "| ADR-062 |" in decision_index
    assert (
        "| RFC-028 | Daily Review Read Model and Deterministic Follow-up View | "
        "Adopted | 2026-07-28 |"
    ) in decision_index
    assert (
        "| ADR-061 | Daily Review as a Non-persistent Read Model | "
        "Accepted | 2026-07-28 |"
    ) in decision_index
    assert (
        "| ADR-062 | Daily Review Source Failure and Availability Semantics | "
        "Accepted | 2026-07-28 |"
    ) in decision_index
    assert (
        "| SP-019 | Daily Review Read Model & Deterministic Follow-up View | "
        "APPROVED / MERGED / POST_MERGE_VERIFIED / "
        "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |"
    ) in roadmap
    assert (
        "> 最近完成的 Product SP：SP-021\n"
        "> 当前 Product SP：None"
    ) in brain
    assert (
        "> SP-019 状态：APPROVED / MERGED / POST_MERGE_VERIFIED / "
        "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
    ) in brain
    assert (
        "> SP-019 规划合并基线："
        "`e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / "
        "Quality Gate run `30205853257` / SUCCESS"
    ) in brain
    assert "> Current main:" not in brain
    assert "Latest Merged SP 与 Latest Completed SP 均为 SP-021" in project_status
    assert "Current Product SP 与 Current Governance Task 均为 None" in project_status


    assert (
        "SP-019 Feature PR #51 已由 Acceptance Evidence Head "
        "`420da28664914fda8ccbecadf90947380ec43473` Squash Merge 为 main "
        "`a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`"
    ) in project_status
    assert "| Current product SP | None" in project_health
    assert "| Current governance task | None" in project_health
    assert (
        "| SP-019 Phase 0 | UserTask Workspace Query Closure / "
        "ACCEPTED |"
    ) in project_health
    assert (
        "| SP-019 Daily Review | MERGED / VERIFIED / ACCEPTED / ARCHIVED |"
    ) in project_health
    assert "| Current main |" not in project_health
    assert (
        "| SP-019 planning merge baseline | "
        "`e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / "
        "run `30205853257` / SUCCESS |"
    ) in project_health
    assert "Current Governance Task: SP-019A" not in brain
    assert "Current governance task | SP-019A" not in project_health
    assert (
        "SP-019 已完成 Squash Merge、ACC-019 A～M 与 post-merge "
        "Quality Gate"
    ) in readme
    assert (
            "GET /daily-review?date=today\n"
            "GET /daily-review?date=yesterday\n"
            "GET /daily-review/action-hints?date=today\n"
            "GET /brief\n"
        "CEO Assistant：今日简报 / 昨日简报"
    ) in readme
    assert (
        "Daily Review 只支持 `today` / `yesterday`，不持久化 Review "
        "snapshot，不支持任意历史日期，不调用 LLM、不主动推送；CLI 与 API "
        "复用同一个服务。"
    ) in readme
    for historical_document in (rfc, adr061, adr062, acceptance):
        assert "SP-020" not in historical_document


def test_sp020_is_merged_reconciled_and_archived() -> None:
    state = _load_state()
    sp020 = state["sp_records"]["SP-020"]
    acc020 = state["acceptance_records"]["ACC-020"]

    assert state["updated_at"] == "2026-08-15"
    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"
    assert state["release_status"]["current_version"] == "0.35.0"
    assert state["release_status"]["previous_published_tag"] == "v0.34.0"

    assert sp020["status"] == (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "FORMAL_ACCEPTANCE_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / "
        "RECONCILED / ARCHIVED"
    )
    assert sp020["planning_baseline_defined"] is True
    assert sp020["planning_baseline_approved"] is True
    assert sp020["approved"] is True
    assert sp020["implementation_started"] is True
    assert sp020["implementation_complete"] is True
    assert sp020["completed"] is True
    assert sp020["reconciled"] is True
    assert sp020["archived"] is True
    assert sp020["approved_implementation_head"] == (
        "1c9b69ee45b4e1545b67ecd841cc217e23d4f38f"
    )
    assert sp020["acceptance_evidence_head"] == (
        "7a0944f4ad1deadefe636bf5abc3d30175de0b4d"
    )
    assert sp020["feature_pr"] == 57
    assert sp020["feature_head"] == (
        "fdbcbe9dc6b63a322e9b1060bdedab76e1e012f7"
    )
    assert sp020["feature_merge_commit"] == (
        "9ea4b72241bd855319231c09fa6b80c112a14305"
    )
    assert sp020["merged_at"] == "2026-08-01T06:29:58Z"
    assert sp020["main_quality_gate"] == "PASSED"
    assert sp020["main_quality_gate_run"] == 30687851816
    assert sp020["post_merge_verification"] == "PASSED"
    assert sp020["reconciliation_pr"] == 58
    assert {
        "reconciliation_merge_commit",
        "reconciled_at",
        "post_reconciliation_quality_gate_run",
    }.isdisjoint(sp020)
    assert sp020["base_commit"] == (
        "934075ceefe39ede3c624b621b7673d62f6d06dd"
    )
    assert sp020["branch"] == (
        "docs/sp-020-local-daily-operating-loop-planning"
    )
    assert sp020["planning_pr"] == 53
    assert sp020["planning_head"] == (
        "d09ec3fa52715e59bcb397587659af3ae0852e33"
    )
    assert sp020["planning_merge_commit"] == (
        "fbd10fb5c4cd3913bb70d0c17cdd6df9de196625"
    )
    assert sp020["planning_merged_at"] == "2026-07-29T09:54:21Z"
    assert sp020["post_planning_quality_gate_run"] == 30441534383
    assert sp020["target_version"] == "0.35.0"
    assert sp020["rfc"] == "RFC-029"
    assert sp020["adrs"] == ["ADR-063", "ADR-064"]
    assert sp020["acceptance"] == "ACC-020 PASSED / FINAL"
    assert sp020["phase_0_status"] == "PASSED"
    assert sp020["phase_1_status"] == "IMPLEMENTED"
    assert sp020["phase_2_status"] == "IMPLEMENTED"
    assert sp020["phase_3_status"] == "IMPLEMENTED"
    assert sp020["implementation_base_commit"] == (
        "1c398ffc3a093ab596dd93fd9f52b5e54bcfb4b2"
    )
    assert sp020["implementation_branch"] == (
        "feat/sp-020-local-daily-operating-loop"
    )
    assert sp020["implementation_authorization_contract"] == (
        "One explicit Owner authorization covers SP-020 implementation; "
        "Phase 0 is an internal mandatory quality gate and does not require "
        "a second authorization after passing"
    )
    assert sp020["reauthorization_triggers"] == (
        "Phase 0 failure, stop condition, approved-scope change, Product SP "
        "split, or new architecture decision"
    )

    assert acc020["status"] == "PASSED / FINAL"
    assert acc020["manual_acceptance"] is True
    assert acc020["independent_evidence_review"] == "APPROVED"
    assert acc020["approved_implementation_head"] == (
        "1c9b69ee45b4e1545b67ecd841cc217e23d4f38f"
    )
    assert acc020["driver_sha256"] == (
        "99695ac3f7544eebf5058db89b2b7d39eece6aec2e042e8f5f90273a7fcae3c5"
    )
    assert acc020["acceptance_evidence_head"] == (
        "7a0944f4ad1deadefe636bf5abc3d30175de0b4d"
    )
    assert acc020["scenarios"] == {
        letter: "PASSED"
        for letter in "ABCDEFGHIJKLMNOPQRSTUV"
    }
    assert acc020["notes"] == [
        (
            "Formal Run ID: ai-lab-acc020-formal-20260730-175832-"
            "eda685f89c274e6cb520c0aaa964b3dc"
        ),
        "Execution: ONE AND ONLY ONE",
        (
            "Frozen Implementation Head: "
            "1c9b69ee45b4e1545b67ecd841cc217e23d4f38f"
        ),
        (
            "Frozen Driver SHA-256: "
            "99695ac3f7544eebf5058db89b2b7d39eece6aec2e042e8f5f90273a7fcae3c5"
        ),
        "Provider Calls: 0",
        "Evidence: 7a0944f4ad1deadefe636bf5abc3d30175de0b4d",
        "Independent Evidence Review: APPROVED",
        "Evidence Package: INTERNALLY CONSISTENT / SECRET-SAFE / APPROVED",
        "Feature PR: #57",
        "Feature Merge Commit: 9ea4b72241bd855319231c09fa6b80c112a14305",
        "Merged At: 2026-08-01T06:29:58Z",
        "Post-Merge main Quality Gate: 30687851816 / SUCCESS",
        "Post-Merge Verification: PASSED",
    ]

    evidence_root = (
        ROOT
        / "docs/acceptance/evidence/ACC-020"
        / "ai-lab-acc020-formal-20260730-175832-"
        "eda685f89c274e6cb520c0aaa964b3dc"
    )
    evidence_index = json.loads(
        (evidence_root / "evidence-index.json").read_text(encoding="utf-8")
    )
    assert evidence_index["frozen_implementation_head"] == (
        "1c9b69ee45b4e1545b67ecd841cc217e23d4f38f"
    )
    assert evidence_index["frozen_driver_sha256"] == (
        "99695ac3f7544eebf5058db89b2b7d39eece6aec2e042e8f5f90273a7fcae3c5"
    )
    assert evidence_index["status"] == "FORMAL_ACCEPTANCE_COMPLETE"
    assert evidence_index["provider_calls"] == 0
    assert evidence_index["scenario_results"] == {
        letter: "PASS"
        for letter in "ABCDEFGHIJKLMNOPQRSTUV"
    }

    paths = {
        "rfc": ROOT
        / "docs/rfc/029-local-daily-operating-loop-review-to-action.md",
        "adr063": ROOT
        / "docs/adr/ADR-063-daily-review-action-hints-pure-deterministic-presentation.md",
        "adr064": ROOT
        / "docs/adr/ADR-064-local-daily-profile-quiescent-backup-restore.md",
        "task": ROOT / "docs/project/SP-020-IMPLEMENTATION-TASK.md",
        "acceptance": ROOT
        / "docs/acceptance/SP-020-local-daily-operating-loop.md",
    }
    text = {
        name: path.read_text(encoding="utf-8-sig")
        for name, path in paths.items()
    }

    assert "- 状态：Adopted" in text["rfc"]
    assert "- 规划审查：APPROVED" in text["rfc"]
    assert "- 规划 PR：#53 / MERGED" in text["rfc"]
    assert (
        "- 规划合并 Commit："
        "`fbd10fb5c4cd3913bb70d0c17cdd6df9de196625`"
    ) in text["rfc"]
    assert (
        "- 规划后 main Quality Gate：`30441534383` / SUCCESS"
    ) in text["rfc"]
    assert (
        "- 产品实施：AUTHORIZED / IMPLEMENTED ON DRAFT PR / "
        "PENDING INDEPENDENT REVIEW"
    ) in text["rfc"]
    assert "- Status: Accepted" in text["adr063"]
    assert "- Status: Accepted" in text["adr064"]
    assert (
        "`load_system_settings()` 默认以 `Path.cwd()` 为 project root，并只从该目录加载"
        in text["rfc"]
    )
    assert (
        "因而从不同 working directory 启动可能静默连接到不同数据目录。"
        in text["rfc"]
    )
    assert (
        "FastAPI lifespan 为长运行 API 进程持有一个 `SystemContainer`；CLI 单次命令通常"
        in text["rfc"]
    )
    assert (
        "`DailyReviewService` 只读取五个 canonical service，不拥有数据库、EventBus、"
        in text["rfc"]
    )
    assert "当前正式入口：" in text["rfc"]
    assert "python -m cli daily-review --date today" in text["rfc"]
    assert (
        "`SystemContainer._run_shutdown()` 在同一流程中两次调用\n"
        "  `SchedulerRuntime.shutdown()`"
    ) in text["rfc"]
    assert (
        "Scheduler 当前实现可重复取消 tick、清空 background\n"
        "  tasks 并关闭 persistence，但 SP-020 Phase 0 必须用正式测试证明幂等"
    ) in text["rfc"]
    assert (
        "Profile 不得依赖调用者的 working directory 决定业务数据位置。"
        in text["adr064"]
    )
    assert (
        "备份合同采用 Quiescent Backup，而不是在线跨库快照"
        in text["adr064"]
    )
    assert (
        "Hint 只能由以下事实确定：\n\n"
        "```text\n"
        "source_type\n"
        "current status\n"
        "reason_code\n"
        "current canonical domain contract\n"
        "```"
    ) in text["adr063"]
    assert "不调用 Provider 或 LLM" in text["adr063"]
    assert "不执行或调度动作" in text["adr063"]
    assert "不拥有数据库、不持久化、不创建 snapshot" in text["adr063"]
    assert (
        "`available_entrypoints` 只列出当前真实存在并符合该动作安全合同的入口。一个\n"
        "`allowed_action` 至少有一个真实、安全入口即可展示，不要求 API、CLI 与 CEO Assistant\n"
        "三者同时存在。尚未存在的入口不得被描述为可用"
    ) in text["adr063"]
    assert (
        "revision、idempotency、durable claim/Saga 与 confirmation 按动作分别声明"
        in text["adr063"]
    )
    assert (
        "user_task + active + user_task.overdue|user_task.due_soon"
        in text["rfc"]
    )
    assert (
        "reminder + scheduled|retrying + reminder.due_soon"
        in text["rfc"]
    )
    assert all(
        action in text["rfc"]
        for action in (
            "resolve_to_task",
            "resolve_to_reminder",
            "resolve_to_work_log",
            "resolve_to_waiting_for",
            "resolve_as_note",
            "dismiss",
        )
    )
    assert (
        "header 缺失时使用 Profile 默认值"
        in text["rfc"]
    )
    assert (
        "显式存在但为空白时，在读取或写入 canonical source 前返回稳定 validation"
        in text["rfc"]
    )
    assert (
        "| Work Log | `wl_...`（另有只读 legacy） | list/get | create only |"
        in text["rfc"]
    )
    assert (
        "Daily Review 继续只读。所有 mutation 委托现有："
        in text["rfc"]
    )
    assert (
        "不得建立 Action 数据库、Review snapshot 数据库、第二套 Command Bus"
        in text["rfc"]
    )
    assert (
        "默认只承诺 Quiescent Backup"
        in text["rfc"]
    )
    assert (
        "当前 `DatabaseManager.backup()` / `restore()` 未实现。"
        in text["rfc"]
    )
    assert (
        "阶段 0 — 产品入口与生命周期门禁"
        in text["rfc"]
    )
    assert (
        "阶段 4 — 持续每日验收"
        in text["rfc"]
    )
    owner_authorization_contract = (
        "SP-020 产品实施需要一次明确的 Owner 授权。\n\n"
        "Phase 0 是同一次 SP-020 实施授权内部的强制质量门禁，不需要在通过后再次获得 Owner\n"
        "授权。Phase 0 失败、触发停止条件、需要改变已批准范围、需要拆分 Product SP，或需要\n"
        "引入新的架构决策时，必须立即停止并重新请求 Owner 决策。"
    )
    assert owner_authorization_contract in text["rfc"]
    assert "每个 Phase 都需要单独 Owner 授权" not in text["rfc"]
    assert "每个 Phase 都需要单独 Owner 授权" not in text["task"]
    assert "每个 Phase 都需要单独 Owner 授权" not in text["acceptance"]
    assert (
        "Phase 0 是同一次实施授权内部的强制质量\n"
        "门禁；通过 Phase 0 后不需要再次请求 Owner 授权。"
    ) in text["task"]

    user_task_revision_contract = (
        "UserTask update:\n"
        "当前 Service 接受调用方 expected_revision；API PATCH 通过 revision 字段传入。\n\n"
        "UserTask complete/cancel:\n"
        "历史 `/tasks/{id}/complete|cancel` 兼容入口仍允许省略调用方 revision，并由 Service\n"
        "读取最新对象后使用 current revision。SP-020 新增的 Review-to-Action 薄 API 与\n"
        "Service 显式接受 `expected_revision`；无论 active 或已处于同一 terminal status，\n"
        "stale revision 都先于 terminal idempotency 检查而 fail closed。\n\n"
        "Review-to-Action decision:\n"
        "UserTask complete/cancel 已增加显式 expected_revision，防止用户依据旧 Daily Review\n"
        "操作已经变化的对象。"
    )
    assert user_task_revision_contract in text["rfc"]
    assert "不是当前能力" not in text["rfc"]
    assert (
        "仅当\nAction Hint 声明 `requires_revision=true` 时，缺失或 stale revision 才必须 fail\n"
        "closed；需要 idempotency key、durable claim/Saga 或 confirmation 的动作分别按自身\n"
        "真实合同验收。"
    ) in text["acceptance"]
    assert (
        "只允许补齐 ACC-020 日常用户闭环实际需要的薄入口委托，不为入口对称性补齐所有领域\n"
        "动作，不复制领域业务逻辑，不追求 API、CLI、CEO Assistant 的完整矩阵对称"
    ) in text["rfc"]
    assert (
        "只补齐 ACC-020 日常用户闭环实际需要的薄入口委托。不得为了入口对称性补齐所有领域\n"
        "动作，不追求 API、CLI、CEO Assistant 的完整矩阵对称"
    ) in text["task"]
    assert (
        "多个 Scheduler tick、一次真实 one-shot job 执行、一个明确\n"
        "   记录起止时间的空闲运行窗口、周期性 health 快照、background task 状态与\n"
        "   `DatabaseManager.connection_count`"
    ) in text["rfc"]
    assert (
        "持续运行证据不得只包含一次瞬时启动和关闭。driver 必须记录一个明确起止时间的运行\n"
        "窗口，并至少覆盖：多个 Scheduler tick、一次真实 one-shot job 执行、一个空闲运行\n"
        "窗口、周期性 health 快照、每次快照的 background task 状态与\n"
        "`DatabaseManager.connection_count`。"
    ) in text["acceptance"]

    assert (
        "Planning Status:\n"
        "PLANNING_BASELINE_APPROVED / MERGED / RECONCILED\n\n"
        "Implementation:\n"
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED /\n"
        "INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED"
    ) in text["task"]
    assert "Phase 0 未通过不得进入 Phase 1。" in text["task"]
    assert "Version change:\nNOT AUTHORIZED" in text["task"]
    assert "Tag:\nNOT AUTHORIZED / UNCHANGED" in text["task"]
    assert "GitHub Release:\nNOT AUTHORIZED / UNCHANGED" in text["task"]

    for letter in "ABCDEFGHIJKLMNOPQRSTUV":
        assert f"## ACC-020-{letter} —" in text["acceptance"]
    assert text["acceptance"].count("\n状态：PASSED") == 22
    assert "状态：PLANNING_BASELINE / NOT_EXECUTED" not in text["acceptance"]
    assert "- 真实 Provider 调用：0" in text["acceptance"]
    assert (
        "任何 Scheduler 重复执行/丢 job、shutdown 非幂等、数据目录静默漂移"
        in text["acceptance"]
    )
    assert (
        "`--prepare-only` 只能生成 `PREPARED_NOT_EXECUTED` 清单"
        in text["acceptance"]
    )
    assert (
        "requires_revision/requires_idempotency_key/requires_confirmation/"
        in text["acceptance"]
    )
    entrypoint_audit = json.loads(
        (
            ROOT / "docs/project/SP-020-ENTRYPOINT-AUDIT.json"
        ).read_text(encoding="utf-8")
    )
    inbox_actions = {
        entry["allowed_action"]: entry
        for entry in entrypoint_audit["entries"]
        if entry["source_type"] == "inbox"
    }
    assert set(inbox_actions) == {
        "resolve_to_task",
        "resolve_to_reminder",
        "resolve_to_work_log",
        "resolve_to_waiting_for",
        "resolve_as_note",
        "dismiss",
    }
    assert all(
        "*" not in entry["existing_api_entrypoint"]
        and "*" not in entry["existing_cli_entrypoint"]
        and entry["saga_contract"] == "InboxResolutionClaim"
        for entry in inbox_actions.values()
    )
    reminder_reschedule = next(
        entry
        for entry in entrypoint_audit["entries"]
        if entry["source_type"] == "reminder"
        and entry["allowed_action"] == "reschedule"
    )
    assert reminder_reschedule["required_arguments"] == [
        "source_id",
        "expected_revision",
        "scheduled_for",
        "timezone",
    ]
    assert (
        reminder_reschedule["idempotency_contract"]
        == "optional supported; not required"
    )
    assert inbox_actions["resolve_to_waiting_for"]["required_arguments"] == [
        "source_id",
        "subject",
        "waiting_on",
        "next_review_at",
        "timezone",
    ]
    assert "confirmation_time" not in json.dumps(entrypoint_audit)
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
    launcher = (
        ROOT / "scripts/start-local-daily.ps1"
    ).read_text(encoding="utf-8-sig")
    assert (
        "Copy-Item .\\config\\local-daily.env.example .\\.env"
        in readme
    )
    assert (
        "& $Python -m cli profile --require-local-daily"
        in readme
    )
    assert all(
        contract in launcher
        for contract in (
            '$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path',
            "Set-Location -LiteralPath $ProjectRoot",
            "& $Python -m cli profile --require-local-daily",
            "--host 127.0.0.1",
        )
    )

    decision_index = (
        ROOT / "docs/project/DECISION_INDEX.md"
    ).read_text(encoding="utf-8-sig")
    assert (
        "| RFC-029 | Local Daily Operating Loop & Review-to-Action Closure | "
        "Adopted | 2026-07-29 |"
    ) in decision_index
    assert (
        "| ADR-063 | Daily Review Action Hints as Pure Deterministic "
        "Presentation | Accepted | 2026-07-29 |"
    ) in decision_index
    assert (
        "| ADR-064 | Local Daily Profile and Quiescent Backup/Restore "
        "Contract | Accepted | 2026-07-29 |"
    ) in decision_index

    known_limitations = (
        ROOT / "docs/project/KNOWN_LIMITATIONS.md"
    ).read_text(encoding="utf-8-sig")
    assert "Waiting-For 人工验收待完成" not in known_limitations
    assert "Follow-up 交互捕获未实现" not in known_limitations
    assert (
        "默认 data root 仍随 working directory 推导"
        in known_limitations
    )
    assert (
        "当前 `SystemContainer` 的同一关闭流程会两次调用 Scheduler shutdown"
        in known_limitations
    )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    assert "### SP-020 本地每日运行闭环规划基线" in changelog
    assert "### SP-019 每日复盘读取模型与确定性跟进视图" in changelog
    assert (
        "全局测试从 692 passed、2 failed 修复为 699 passed、0 failed"
        in changelog
    )
    assert "non-real 测试：694 passed、0 failed、26 warnings" in changelog
    assert "单独 real Provider 测试：5 passed、0 failed" in changelog
    assert (
        "当时全局 real 模式仍有 4 个 async fixture collection error"
        in changelog
    )
    assert (
        "Stability Gate：PASS（普通测试 0 failed，DeepSeek 真实验证通过）"
        in changelog
    )
    assert "全量 647 项测试通过，零回归" in changelog
    assert "SP-019 保持 candidate、未批准、未启动" not in changelog

    project_health = (
        ROOT / "docs/project/PROJECT_HEALTH.md"
    ).read_text(encoding="utf-8-sig")
    assert "| Main |" not in project_health
    assert "| Main Quality Gate |" not in project_health
    assert (
        "| SP-019 reconciliation merge main | "
        "`934075ceefe39ede3c624b621b7673d62f6d06dd` / "
        "run `30387237549` / SUCCESS |"
    ) in project_health
    assert (
        "| SP-020 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / "
        "RECONCILED / ARCHIVED |"
    ) in project_health
    assert (
        "| Local Daily Loop / SP-020 | Integrated / Verified / Archived | "
        "RFC-029 Adopted；ADR-063、ADR-064 Accepted；ACC-020 PASSED / "
        "FINAL；main Quality Gate SUCCESS |"
    ) in project_health


def test_sp020_current_acceptance_state_is_consistent_across_documents() -> None:
    current_status = (
        "SP-020:\n"
        "APPROVED /\n"
        "MERGED /\n"
        "MAIN_QUALITY_GATE_PASSED /\n"
        "ACC_020_PASSED /\n"
        "INDEPENDENT_EVIDENCE_REVIEW_APPROVED /\n"
        "RECONCILED /\n"
        "ARCHIVED\n\n"
        "ACC-020:\n"
        "PASSED / FINAL\n\n"
        "Approved Implementation Head:\n"
        "1c9b69ee45b4e1545b67ecd841cc217e23d4f38f\n\n"
        "Acceptance Evidence Head:\n"
        "7a0944f4ad1deadefe636bf5abc3d30175de0b4d\n\n"
        "Formal Run:\n"
        "ai-lab-acc020-formal-20260730-175832-"
        "eda685f89c274e6cb520c0aaa964b3dc\n\n"
        "Provider Calls:\n"
        "0\n\n"
        "Evidence Review:\n"
        "APPROVED\n\n"
        "Feature Merge Commit:\n"
        "9ea4b72241bd855319231c09fa6b80c112a14305\n\n"
        "Main Quality Gate:\n"
        "30687851816 / SUCCESS\n\n"
        "Reconciliation PR:\n"
        "58"
    )
    current_documents = (
        ROOT / "docs/project/PROJECT_BRAIN.md",
        ROOT / "docs/project/PROJECT_STATUS.md",
        ROOT / "docs/project/PROJECT_HEALTH.md",
        ROOT / "docs/acceptance/SP-020-local-daily-operating-loop.md",
        ROOT / "docs/project/SP-020-IMPLEMENTATION-TASK.md",
    )

    for path in current_documents:
        assert current_status in path.read_text(encoding="utf-8-sig")


def test_sp020_discarded_rehearsal_and_driver_contract_are_explicit() -> None:
    acceptance = (
        ROOT / "docs/acceptance/SP-020-local-daily-operating-loop.md"
    ).read_text(encoding="utf-8-sig")
    task = (
        ROOT / "docs/project/SP-020-IMPLEMENTATION-TASK.md"
    ).read_text(encoding="utf-8-sig")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    combined = f"{acceptance}\n{task}\n{changelog}"

    assert "bd858807262aa1b89cdb80644895afa970edcf64" in combined
    assert "0782c6c1d217ad5e6bac78e93cc47e3925d17c3c79fabff0135836c4d072a36c" in combined
    assert (
        "INVALID_ACCEPTANCE_HARNESS /\nDISCARDED /\n"
        "INSUFFICIENT_SCENARIO_ASSERTION_COVERAGE"
    ) in acceptance
    assert "原“22/22 PASS”结论无效" in acceptance
    assert "它不是产品失败" in acceptance
    assert "Approved Implementation Head 仍未冻结" in task
    assert "ACC-020 仍未执行" in task
    assert "cf0444d27ed47aef8177f5eeea2efe5f3fdd14fb" in combined
    assert (
        "5f2a8f51e5d964a7e66b58f800bd26eba70781bca7754a81b38e6664d5c72147"
        in combined
    )
    assert (
        "INVALID_ACCEPTANCE_HARNESS /\nDISCARDED /\n"
        "FALSE_POSITIVE_SCENARIO_ASSERTIONS"
    ) in acceptance
    assert "f2d7dd3d4c5cf6c999b8cdfd35a76d140e7fbae6" in combined
    assert (
        "b6546cc3d30e2b3a3e37cef377267caa4714f1891e522e07111cbee9209d0be5"
        in combined
    )
    assert (
        "INVALID_ACCEPTANCE_HARNESS /\nDISCARDED /\n"
        "SHUTDOWN_CALL_SUCCESS_NOT_ASSERTED"
    ) in acceptance
    assert "它不是产品失败，不改变\nACC-020 A～V 的机器状态" in acceptance
    assert "每项包含 `expected`、`actual`、`passed` 与真实 `evidence_path`" in acceptance
    assert "单独调用描述性 PASS helper\n不能绕过断言" in task


def test_docs001_is_reconciled_and_archived() -> None:
    state = _load_state()
    docs001 = state["governance_tasks"]["DOCS-001"]

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_planned_governance_item"] is None
    assert docs001 == {
        "name": (
            "Repository Markdown Chinese Standardization and "
            "Documentation Governance"
        ),
        "type": "DOCUMENTATION_GOVERNANCE",
        "base_commit": "6d888725dbe8f31f77c46d2ebdc2dd9ef8612d29",
        "branch": "docs/docs-001-markdown-chinese-governance",
        "status": (
            "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
            "RECONCILED / ARCHIVED"
        ),
        "approved_head": "d7a6662dddaac87b41562e2348f69e04112b2be4",
        "pr_number": 55,
        "merge_commit": "2d04f1b8574fde43b1d64a53d1ad22573073a4ef",
        "merged_at": "2026-07-29T14:43:26Z",
        "main_quality_gate_run": 30462290819,
        "main_quality_gate": "SUCCESS",
        "post_merge_reconciled": True,
        "product_code_changed": False,
        "version_changed": False,
        "tag_changed": False,
        "release_changed": False,
    }

    assert state["current_version"] == "0.35.0"
    assert state["release_status"]["previous_published_tag"] == "v0.34.0"

    current_governance_docs = "\n".join(
        (
            (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(
                encoding="utf-8-sig"
            ),
            (ROOT / "docs/project/PROJECT_STATUS.md").read_text(
                encoding="utf-8-sig"
            ),
            (ROOT / "docs/project/PROJECT_HEALTH.md").read_text(
                encoding="utf-8-sig"
            ),
        )
    )
    assert "176 个 Git 跟踪 Markdown 文件" in current_governance_docs
    assert "30462290819" in current_governance_docs
    assert "INDEPENDENT_EVIDENCE_REVIEW_APPROVED" in current_governance_docs
    assert "ACC-020 | PASSED / FINAL" in current_governance_docs
    assert "FINAL_RECONCILED / ARCHIVED" in current_governance_docs
    assert "Current Governance Task: DOCS-001" not in current_governance_docs
    assert "当前治理任务：DOCS-001" not in current_governance_docs


def test_rel035_final_publication_reconciliation_is_locked() -> None:
    state = _load_state()
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    rel035 = state["governance_tasks"]["REL-035"]
    published_release = state["release_status"]["published_releases"]["v0.35.0"]

    assert state["current_governance_task"] is None
    assert state["git_branch"] == "main"
    assert state["current_sp"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"
    assert pyproject["project"]["version"] == "0.35.0"

    assert rel035 == {
        "name": "v0.35.0 Alpha Release Consolidation",
        "type": "RELEASE_GOVERNANCE",
        "base_commit": "5456ed2406fa54443a02b436e2684bf90698afea",
        "planning_merge_commit": "e596c3331ed86dbba3aeded3ccd61517d1901559",
        "implementation_base_commit": "e596c3331ed86dbba3aeded3ccd61517d1901559",
        "branch": "chore/rel-035-v035-alpha-release-consolidation",
        "final_reconciliation_branch": "docs/rel-035-final-release-reconciliation",
        "status": (
            "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
            "POST_MERGE_RECONCILED / RELEASE_HEAD_FROZEN / "
            "TAG_REMOTE_VERIFIED / GITHUB_PRE_RELEASE_PUBLISHED / "
            "FINAL_RECONCILED / ARCHIVED"
        ),
        "target_version": "0.35.0",
        "target_release_name": "v0.35.0 Alpha — Local Daily Operating Loop",
        "release_type": "prerelease",
        "binary_assets": 0,
        "implementation_approved": True,
        "version_changed": True,
        "approved_head": "f39045410b7aacfa2c14356e5e519f8fc3b440b9",
        "pr_number": 60,
        "merge_commit": "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
        "merged_at": "2026-08-02T11:00:45Z",
        "main_quality_gate_run": 30744879482,
        "main_quality_gate": "SUCCESS",
        "release_head": "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
        "tag": "v0.35.0",
        "tag_type": "annotated",
        "tag_object_sha": "99de47895b967bc41c3b1dcb3d2caaa630fcd4de",
        "tag_peeled_commit": "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
        "tag_authorized": True,
        "tag_created": True,
        "github_release_authorized": True,
        "github_release_published": True,
        "github_release_id": 363770731,
        "github_release_name": "v0.35.0 Alpha — Local Daily Operating Loop",
        "github_release_type": "prerelease",
        "github_release_draft": False,
        "github_release_published_at": "2026-08-02T11:32:43Z",
        "github_release_url": (
            "https://github.com/y19870785/ai-lab-os/releases/tag/v0.35.0"
        ),
        "post_merge_reconciled": True,
        "final_reconciled": True,
        "archived": True,
        "product_code_changed": False,
        "schema_changed": False,
        "migration_changed": False,
        "dependencies_changed": False,
        "ci_changed": False,
    }
    assert published_release["status"] == "PRE_RELEASE_PUBLISHED / REMOTE_VERIFIED"
    assert published_release["tag"] == "v0.35.0"
    assert published_release["tag_object_sha"] == rel035["tag_object_sha"]
    assert published_release["tag_peeled_commit"] == rel035["release_head"]
    assert published_release["github_release_id"] == 363770731
    assert published_release["draft"] is False
    assert published_release["binary_assets"] == 0
    assert published_release["github_release_published"] is True
    assert state["release_status"]["publication_status"] == "PRE_RELEASE_PUBLISHED"
    assert state["release_status"]["published_tag"] == "v0.35.0"
    assert state["release_status"]["previous_published_tag"] == "v0.34.0"
    assert state["release_status"]["binary_assets"] == "none"

    plan = (ROOT / "docs/project/REL-035-V035-ALPHA-RELEASE-PLAN.md").read_text(
        encoding="utf-8"
    )
    task = (ROOT / "docs/project/REL-035-IMPLEMENTATION-TASK.md").read_text(
        encoding="utf-8"
    )
    release_notes = (ROOT / "docs/releases/v0.35.0-alpha.md").read_text(
        encoding="utf-8"
    )
    reconciliation_path = ROOT / "docs/project/REL-035-FINAL-RECONCILIATION.md"
    assert reconciliation_path.is_file()
    reconciliation = reconciliation_path.read_text(encoding="utf-8")

    required_plan_contracts = (
        "v0.35.0 Alpha — Local Daily Operating Loop",
        "No destructive database migration is required.",
        "No existing v0.34.0 table rewrite is required.",
        "No legacy data import is required.",
        "No dual-write migration is required.",
        "followups.db",
        "waiting_for_items",
        "waiting_for_events",
        "CREATE TABLE IF NOT EXISTS",
        "CREATE INDEX IF NOT EXISTS",
    )
    assert all(marker in plan for marker in required_plan_contracts)

    combined_contracts = f"{plan}\n{task}"
    required_config_contracts = (
        "AI_LAB_DATA_DIR",
        "AI_LAB_SQLITE_DIR",
        "AI_LAB_TIMEZONE",
        "AI_LAB_PROVIDER_MODE",
        "AI_LAB_API_TOKEN",
        "AI_LAB_TENANT_ID",
        "AI_LAB_WORKSPACE_ID",
        "AI_LAB_NAMESPACE",
    )
    assert all(marker in combined_contracts for marker in required_config_contracts)

    required_authorization_events = (
        "Planning PR Approval",
        "Implementation Approval",
        "Release PR Merge",
        "Tag Authorization",
        "GitHub Release Authorization",
    )
    assert all(marker in combined_contracts for marker in required_authorization_events)

    required_validation_evidence = (
        "Governance + Version | `37 passed`",
        "pytest non-real | `1708 passed / 27 warnings`",
        "Full pytest | `1708 passed / 5 skipped / 27 warnings`",
        "AI_LAB_SQLITE_DIR` 位于 `AI_LAB_DATA_DIR` 外",
        "AI_LAB_TIMEZONE=Invalid/REL035",
        "缺失 `AI_LAB_PROVIDER_MODE`",
        "缺失 `AI_LAB_ENABLE_DAILY_REVIEW`",
        "Unexpected Files Created: NO",
        "Provider Calls: 0",
    )
    assert all(marker in release_notes for marker in required_validation_evidence)

    assert (
        "Planning Baseline Original State：\n\n```text\nREL-035:\n"
        "PLANNING_BASELINE_DEFINED /\nIMPLEMENTATION_NOT_APPROVED /\nNOT_STARTED"
    ) in plan
    assert "Current State）：`FINAL_RECONCILED / ARCHIVED`" in plan
    assert "chore/rel-035-v035-alpha-release-consolidation" in task
    assert "Release PR:\n#60" in task
    assert "Source Version:\n0.35.0" in task
    assert "不得重新执行正式 ACC-020 A～V" in task
    assert "Implementation Status:\nFINAL_RECONCILED /\nARCHIVED" in task
    assert "PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED" in release_notes
    assert "GitHub Release ID：`363770731`" in release_notes
    assert "Tag Object：`99de47895b967bc41c3b1dcb3d2caaa630fcd4de`" in release_notes
    assert "Published At：`2026-08-02T11:32:43Z`" in release_notes
    assert "Binary Assets：`0`" in release_notes
    assert "GitHub automatic source archives" in release_notes
    assert "经过授权的\n确定性状态规范化正文" in release_notes
    assert "发布前候选快照" in release_notes
    assert "不是产品缺陷、测试失败或发布回滚" in release_notes

    required_reconciliation_evidence = (
        "REL-035-FINAL",
        "e596c3331ed86dbba3aeded3ccd61517d1901559",
        "f39045410b7aacfa2c14356e5e519f8fc3b440b9",
        "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
        "30744879482 / SUCCESS",
        "99de47895b967bc41c3b1dcb3d2caaa630fcd4de",
        "363770731",
        "2026-08-02T11:32:43Z",
        "Provider Calls | `0`",
        "RELEASE_BODY_GENERATION_CONTRACT_MISMATCH",
        "POWERSHELL_EMPTY_ARRAY_INLINE_COUNT_MISJUDGMENT",
        "远端影响：NONE",
        "Product Code Changed: false",
        "FINAL_RECONCILED / ARCHIVED",
    )
    assert all(marker in reconciliation for marker in required_reconciliation_evidence)

    current_docs = {
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8-sig"),
        "PROJECT_STATUS.md": (ROOT / "docs/project/PROJECT_STATUS.md").read_text(
            encoding="utf-8-sig"
        ),
        "PROJECT_BRAIN.md": (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(
            encoding="utf-8-sig"
        ),
        "PROJECT_HEALTH.md": (ROOT / "docs/project/PROJECT_HEALTH.md").read_text(
            encoding="utf-8-sig"
        ),
        "ROADMAP.md": (ROOT / "docs/project/ROADMAP.md").read_text(
            encoding="utf-8-sig"
        ),
        "VERSION_MATRIX.md": (ROOT / "docs/project/VERSION_MATRIX.md").read_text(
            encoding="utf-8-sig"
        ),
        "RELEASE_CHECKLIST.md": (
            ROOT / "docs/project/RELEASE_CHECKLIST.md"
        ).read_text(encoding="utf-8-sig"),
    }
    combined_current = "\n".join(current_docs.values())
    assert "v0.35.0 Alpha / GitHub Pre-release Published" in current_docs["README.md"]
    assert "当前 Governance Task：** None" in current_docs["ROADMAP.md"]
    assert "FINAL_RECONCILED / ARCHIVED" in combined_current
    assert "PRE_RELEASE_PUBLISHED" in combined_current
    assert "它仍不是 production-ready" in current_docs["README.md"]
    assert (
        "不是\nproduction-ready、enterprise-ready、stable release 或 "
        "general availability"
    ) in reconciliation

    for forbidden_positive_claim in (
        "Maturity: Production-ready",
        "Maturity: Enterprise-ready",
        "Release Stage: Stable",
        "Release Stage: General Availability",
        "成熟度：Production-ready",
        "成熟度：Enterprise-ready",
        "发布阶段：Stable Release",
        "发布阶段：General Availability",
    ):
        assert forbidden_positive_claim not in combined_current

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    assert "## [Unreleased]" in changelog
    assert "## [0.35.0] - 2026-08-02" in changelog

    tracked_markdown = subprocess.run(
        ["git", "ls-files", "*.md", "*.markdown"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    inventory = (ROOT / "docs/project/MARKDOWN_INVENTORY.md").read_text(
        encoding="utf-8-sig"
    )
    assert len(tracked_markdown) == 215
    assert "- Git 跟踪 Markdown：215" in inventory
    assert "- 仓库自有且纳入范围：215" in inventory
    assert "- 新增中文治理文档：39" in inventory
    assert "docs/project/REL-035-FINAL-RECONCILIATION.md" in inventory

    limitations = (ROOT / "docs/project/KNOWN_LIMITATIONS.md").read_text(
        encoding="utf-8-sig"
    )
    assert "GitHub Pre-release Published" in limitations
    assert (
        "该 Alpha Pre-release 仍不是 production-ready、"
        "enterprise-ready、stable release 或\ngeneral availability"
    ) in limitations

    stale_current_limitations = (
        "Daily Review 没有正式 CLI",
        "本地日常运行 Profile 尚未实现",
        "Action Hint 尚未实现",
        "Scheduler shutdown 需正式幂等门禁",
    )
    assert all(marker not in limitations for marker in stale_current_limitations)


def test_strat001_strategy_and_ownership_baseline_is_consistent() -> None:
    state = _load_state()
    strategy = (ROOT / "docs/project/PRODUCT_STRATEGY.md").read_text(
        encoding="utf-8-sig"
    )
    ownership = (ROOT / "docs/project/CAPABILITY_OWNERSHIP.md").read_text(
        encoding="utf-8-sig"
    )
    rfc = (
        ROOT / "docs/rfc/031-agent-shell-trusted-business-core-separation.md"
    ).read_text(encoding="utf-8-sig")
    adr067 = (
        ROOT / "docs/adr/ADR-067-hermes-first-replaceable-agent-shell.md"
    ).read_text(encoding="utf-8-sig")
    adr068 = (
        ROOT / "docs/adr/ADR-068-ai-lab-business-fact-action-authority.md"
    ).read_text(encoding="utf-8-sig")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8-sig")
    project_status = (ROOT / "docs/project/PROJECT_STATUS.md").read_text(
        encoding="utf-8-sig"
    )
    reconciliation = (
        ROOT / "docs/project/STRAT-001-POST-MERGE-RECONCILIATION.md"
    ).read_text(encoding="utf-8-sig")
    limitations = (ROOT / "docs/project/KNOWN_LIMITATIONS.md").read_text(
        encoding="utf-8-sig"
    )

    strat = state["governance_tasks"]["STRAT-001"]
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_planned_governance_item"] is None
    assert state["current_version"] == "0.35.0"
    assert strat["type"] == "PRODUCT_STRATEGY_GOVERNANCE"
    assert strat["audit_base"] == "5f91d9da224daa9fbb2e68f7a3ba685411e93904"
    assert strat["latest_validated_main_base"] == (
        "e4599632e38483780ef422c731a77bc01e85576c"
    )
    assert strat["latest_validated_main_context"] == (
        "QUALITY-002 / PR #64 / MERGED / APPLICATION_DAY_TEST_DETERMINISTIC"
    )
    assert strat["planning_pr"] == 63
    assert strat["status"] == (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "POST_MERGE_RECONCILED / ARCHIVED"
    )
    assert strat["planning_pr_creation_authorized"] is True
    assert strat["planning_baseline_approved"] is True
    assert strat["direction_review_status"] == "INITIAL_DIRECTION_REVIEW_PASSED"
    assert strat["independent_review_status"] == "FINAL_REVIEW_PASSED"
    assert strat["ready_authorized"] is True
    assert strat["merge_authorized"] is True
    assert strat["approved_head"] == "4b34b8ea5b6e62f97a30e15ea333aa3a55e2aa1e"
    assert strat["merge_base"] == "e4599632e38483780ef422c731a77bc01e85576c"
    assert strat["merge_commit"] == "b644c38064117a4dcb906c8607c782b67aedf1a6"
    assert strat["merged_at"] == "2026-08-05T19:20:21Z"
    assert strat["main_quality_gate_run"] == 31038950753
    assert strat["main_quality_gate"] == "SUCCESS"
    assert strat["post_merge_reconciled"] is True
    assert strat["archived"] is True
    assert "MERGED" in strat["status"]
    assert "planning_approved" not in strat
    assert strat["roadmap_order"] == [
        "STRAT-001",
        "ARCH-001",
        "SP-021",
        "INT-001",
        "PILOT-001",
        "REL-036",
    ]
    assert strat["rfc"] == "RFC-031 / ADOPTED"
    assert strat["adrs"] == ["ADR-067 / ACCEPTED", "ADR-068 / ACCEPTED"]
    assert strat["superseded_pr"] == {
        "number": 62,
        "head": "31cf7125b2543fb2d29ed38f373ddcebe4170b70",
        "status": (
            "CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / "
            "IMPLEMENTATION_NEVER_AUTHORIZED"
        ),
        "closed_at": "2026-08-05T19:33:50Z",
    }
    for unchanged in (
        "product_code_changed",
        "schema_changed",
        "migration_changed",
        "runtime_behavior_changed",
        "version_changed",
        "tag_changed",
        "release_changed",
    ):
        assert strat[unchanged] is False

    combined = f"{strategy}\n{ownership}\n{rfc}\n{adr067}\n{adr068}\n{roadmap}"
    for principle in (
        "Hermes Memory 不是业务事实源",
        "Hermes Conversation 不是审批事实源",
        "Hermes Tool Response 不是最终成功证明",
        "Hermes 不得直接访问 AI-Lab 数据库",
        "AI-Lab 不得 import",
        "Hermes 是第一个首选但可替换",
        "业务 Reminder/Scheduler",
        "MCP 可以作为 Adapter transport 候选",
    ):
        assert principle in combined
    assert (
        "实际执行可以由 Agent Shell、AI-Lab 的正式外部系统 Adapter，或其他受控 "
        "Execution\nAdapter 承担"
    ) in combined
    assert "Shell 执行，AI-Lab 控制高风险业务动作" not in combined
    assert (
        "STRAT-001 → ARCH-001 → SP-021 → INT-001 → PILOT-001 → REL-036"
        in roadmap
    )
    assert "Status: Accepted" in adr067
    assert "Status: Accepted" in adr068
    assert "状态：Adopted" in rfc
    assert "Accepted by: STRAT-001 / PR #63" in adr067
    assert "Accepted by: STRAT-001 / PR #63" in adr068
    assert "Adopted by：PR #63" in rfc
    for evidence in (
        "b644c38064117a4dcb906c8607c782b67aedf1a6",
        "31038950753 / SUCCESS",
        "POST_MERGE_RECONCILED / ARCHIVED",
        "CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001",
        "ARCH-001 / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION",
    ):
        assert evidence in reconciliation
    assert "QUALITY-003 Candidate — DeepSeek Real Brief Contract Audit" in limitations
    assert "daily_review.date_invalid" in limitations
    assert "REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED" in limitations
    assert "INT-001 已实现" in project_status
    assert "main Quality Gate `31324821391`" in project_status


def test_arch001_post_merge_reconciliation_is_consistent() -> None:
    state = _load_state()
    arch = state["governance_tasks"]["ARCH-001"]
    plan = (
        ROOT / "docs/project/ARCH-001-TRUSTED-INTERACTION-ARCHITECTURE.md"
    ).read_text(encoding="utf-8-sig")
    rfc = (
        ROOT / "docs/rfc/032-trusted-interaction-boundary-adapter-contract.md"
    ).read_text(encoding="utf-8-sig")
    adr_paths = [
        ROOT / "docs/adr/ADR-069-shell-neutral-versioned-interaction-contract.md",
        ROOT / "docs/adr/ADR-070-preview-confirmation-ai-lab-canonical-facts.md",
        ROOT / "docs/adr/ADR-071-verified-result-required-before-final-success.md",
        ROOT / "docs/adr/ADR-072-identity-workspace-mapping-fail-closed.md",
    ]
    adrs = [path.read_text(encoding="utf-8-sig") for path in adr_paths]
    reconciliation = (
        ROOT / "docs/project/ARCH-001-POST-MERGE-RECONCILIATION.md"
    ).read_text(encoding="utf-8-sig")

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["next_planned_governance_item"] is None
    assert state["current_version"] == "0.35.0"
    assert arch["base_commit"] == "7bf12b1f4206608f0c67223546e8400eb9066c8e"
    assert arch["status"] == (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "POST_MERGE_RECONCILED / ARCHIVED"
    )
    assert arch["planning_authorized"] is True
    assert arch["independent_review_status"] == "FINAL_REVIEW_PASSED"
    assert arch["ready_authorized"] is True
    assert arch["merge_authorized"] is True
    assert arch["implementation_approved"] is False
    assert arch["planning_pr"] == 66
    assert arch["approved_head"] == "5edbb37da6bf9d4b7dd98f5d0e860c695a08ce90"
    assert arch["merge_base"] == "7bf12b1f4206608f0c67223546e8400eb9066c8e"
    assert arch["merge_commit"] == "4f9eab191fc0d99898ee69a2b42912017e4740e3"
    assert arch["merged_at"] == "2026-08-09T08:37:05Z"
    assert arch["main_quality_gate_run"] == 31303951232
    assert arch["main_quality_gate"] == "SUCCESS"
    assert arch["post_merge_reconciled"] is True
    assert arch["archived"] is True
    assert arch["reconciliation"] == (
        "ARCH-001A / SELF-CLOSING / NO_RECURSIVE_RECONCILIATION"
    )
    assert arch["rfc"] == "RFC-032 / ADOPTED"
    assert arch["adrs"] == [
        "ADR-069 / ACCEPTED",
        "ADR-070 / ACCEPTED",
        "ADR-071 / ACCEPTED",
        "ADR-072 / ACCEPTED",
    ]
    assert arch["follow_up_tasks"] == {
        "SP-021": (
            "NEXT_CANDIDATE / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION / "
            "IMPLEMENTATION_NOT_APPROVED"
        ),
        "INT-001": (
            "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
            "POST_MERGE_RECONCILED / ARCHIVED"
        ),
        "PILOT-001": PILOT_001_STATUS,
        "REL-036": "NOT_STARTED / NOT_APPROVED",
    }
    assert arch["quality_003"] == (
        "CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / "
        "NOT_STARTED / NOT_AUTHORIZED"
    )
    assert "2026-08-09 accidental reproduction" in arch["quality_003_observation"]
    assert arch["quality_004"] == (
        "CANDIDATE / SAFETY_RELEVANT / NON_BLOCKING_FOR_ARCH_001 / "
        "NOT_STARTED / NOT_AUTHORIZED"
    )
    quality = state["quality_candidates"]
    assert quality["QUALITY-003"]["authorized"] is False
    assert quality["QUALITY-004"]["authorized"] is True
    assert quality["QUALITY-004"]["required_guard"] == (
        "--run-real-provider AND AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1"
    )
    assert arch["superseded_pr"] == {
        "number": 62,
        "head": "31cf7125b2543fb2d29ed38f373ddcebe4170b70",
        "status": (
            "CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / "
            "IMPLEMENTATION_NEVER_AUTHORIZED"
        ),
    }
    for unchanged in (
        "product_code_changed",
        "schema_changed",
        "migration_changed",
        "runtime_behavior_changed",
        "dependencies_changed",
        "version_changed",
        "tag_changed",
        "release_changed",
    ):
        assert arch[unchanged] is False

    assert "状态：Adopted" in rfc
    assert "Adopted by：ARCH-001 / PR #66" in rfc
    assert all("Status: Accepted" in adr for adr in adrs)
    assert all("Accepted by: ARCH-001 / PR #66" in adr for adr in adrs)
    combined = "\n".join([plan, rfc, *adrs, reconciliation])
    required_contracts = (
        "Hermes Memory != Business Fact Source",
        "Hermes Conversation != Approval Fact Source",
        "Hermes Tool Response != Final Success Proof",
        "View",
        "Preview",
        "Confirm",
        "Cancel",
        "Modify",
        "Status",
        "Verified Result",
        "Recovery",
        "trusted-interaction/v1",
        "Shell-neutral",
        "Transport-neutral",
        "fail closed",
        "Tool response 或 HTTP 2xx",
        "CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001",
    )
    assert all(marker in combined for marker in required_contracts)
    for evidence in (
        "31303951232 / SUCCESS",
        "22 files",
        "ARCH-001A / SELF-CLOSING / NO_RECURSIVE_RECONCILIATION",
        "2026-08-09 accidental reproduction",
        "QUALITY-004 Candidate — Real-Provider Credential Isolation Guard",
        "Product code changed：No",
        "Schema / Migration changed：No",
        "Runtime changed：No",
        "Dependencies / lock files changed：No",
        "CLOSED / DRAFT / NOT_MERGED / SUPERSEDED_BY_STRAT_001",
    ):
        assert evidence in reconciliation
    assert "ARCH-001B" in reconciliation
    assert "不创建 ARCH-001B" in reconciliation

    inventory = (ROOT / "docs/project/MARKDOWN_INVENTORY.md").read_text(
        encoding="utf-8-sig"
    )
    decision_index = (ROOT / "docs/project/DECISION_INDEX.md").read_text(
        encoding="utf-8-sig"
    )
    for path in [
        "docs/project/ARCH-001-TRUSTED-INTERACTION-ARCHITECTURE.md",
        "docs/project/ARCH-001-POST-MERGE-RECONCILIATION.md",
        "docs/rfc/032-trusted-interaction-boundary-adapter-contract.md",
        "docs/adr/ADR-069-shell-neutral-versioned-interaction-contract.md",
        "docs/adr/ADR-070-preview-confirmation-ai-lab-canonical-facts.md",
        "docs/adr/ADR-071-verified-result-required-before-final-success.md",
        "docs/adr/ADR-072-identity-workspace-mapping-fail-closed.md",
    ]:
        assert path in inventory
    for decision in ("RFC-032", "ADR-069", "ADR-070", "ADR-071", "ADR-072"):
        assert decision in decision_index


def test_sp021_post_merge_reconciliation_state_is_consistent() -> None:
    state = _load_state()
    sp021 = state["sp_records"]["SP-021"]
    acc021 = state["acceptance_records"]["ACC-021"]
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["next_candidate_sp"] is None
    assert sp021["base_commit"] == "072276207ec0cc0d69372ef38e833c3e1b72ae90"
    assert sp021["status"] == (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "POST_MERGE_RECONCILED / ARCHIVED"
    )
    assert sp021["implementation_authorized"] is True
    assert sp021["implementation_started"] is True
    assert sp021["implementation_complete"] is True
    assert sp021["independent_review_status"] == "FINAL_REVIEW_PASSED"
    assert sp021["ready_authorized"] is True
    assert sp021["merge_authorized"] is True
    assert sp021["implementation_pr"] == 68
    assert sp021["approved_head"] == "3c899d6a0d83d3d546ce0eb38ec921181dbe2d81"
    assert sp021["merge_base"] == "072276207ec0cc0d69372ef38e833c3e1b72ae90"
    assert sp021["merge_commit"] == "e59091d5a54009ac87164433422c204144d21234"
    assert sp021["merged_at"] == "2026-08-09T11:48:19Z"
    assert sp021["main_quality_gate_run"] == 31311699187
    assert sp021["main_quality_gate"] == "SUCCESS"
    assert sp021["post_merge_reconciled"] is True
    assert sp021["archived"] is True
    assert sp021["current_product_sp"] is False
    assert sp021["reconciliation"] == (
        "SP-021A / SELF_CLOSING / NO_RECURSIVE_RECONCILIATION"
    )
    assert sp021["schema_changed"] is True
    assert sp021["migration_changed"] is True
    assert sp021["schema_initialization_changed"] is True
    assert sp021["standalone_migration_file_changed"] is False
    assert "no standalone migration file" in sp021["migration_change_meaning"]
    assert sp021["follow_up_tasks"] == {
        "INT-001": (
            "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
            "POST_MERGE_RECONCILED / ARCHIVED"
        ),
        "PILOT-001": PILOT_001_STATUS,
        "REL-036": "NOT_STARTED / NOT_APPROVED",
    }
    assert acc021["status"] == "PASSED / FINAL"
    assert acc021["independent_review_status"] == "FINAL_REVIEW_PASSED"
    assert acc021["approved_implementation_head"] == sp021["approved_head"]
    assert acc021["merge_commit"] == sp021["merge_commit"]
    assert acc021["main_quality_gate_run"] == sp021["main_quality_gate_run"]
    assert acc021["main_quality_gate"] == "SUCCESS"
    assert set(acc021["scenarios"]) == set("ABCDEFGHIJKLMNOPQR")
    assert set(acc021["scenarios"].values()) == {"PASSED"}
    assert state["quality_candidates"]["QUALITY-003"]["authorized"] is False
    assert state["quality_candidates"]["QUALITY-004"]["authorized"] is True
    assert state["current_version"] == "0.35.0"
    assert sp021["dependencies_changed"] is False
    assert sp021["version_changed"] is False
    assert sp021["tag_changed"] is False
    assert sp021["release_changed"] is False

    implementation = (
        ROOT / "docs/project/SP-021-CANONICAL-TRUSTED-INTERACTION-DOMAIN.md"
    ).read_text(encoding="utf-8-sig")
    acceptance = (
        ROOT / "docs/acceptance/SP-021-canonical-trusted-interaction-domain.md"
    ).read_text(encoding="utf-8-sig")
    reconciliation_path = (
        ROOT / "docs/project/SP-021-POST-MERGE-RECONCILIATION.md"
    )
    reconciliation = reconciliation_path.read_text(encoding="utf-8-sig")
    inventory = (ROOT / "docs/project/MARKDOWN_INVENTORY.md").read_text(
        encoding="utf-8-sig"
    )
    assert reconciliation_path.is_file()
    assert "docs/project/SP-021-POST-MERGE-RECONCILIATION.md" in inventory
    combined = f"{implementation}\n{acceptance}\n{reconciliation}"
    for marker in (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED",
        "ACC-021 A～R",
        "PASSED / FINAL",
        "SELF_CLOSING",
        "NO_RECURSIVE_RECONCILIATION",
        "Interaction",
        "Preview",
        "Confirmation",
        "Approval",
        "Execution",
        "VerifiedResult",
        "CanonicalCommitEvidence",
        "Recovery",
        "FailureInfo",
        "Workspace",
        "idempotency",
        "ACC-021",
    ):
        assert marker in combined
    current_documents = "\n".join(
        (ROOT / path).read_text(encoding="utf-8-sig")
        for path in (
            "README.md",
            "docs/project/PROJECT_BRAIN.md",
            "docs/project/PROJECT_STATUS.md",
            "docs/project/PROJECT_HEALTH.md",
            "docs/project/ROADMAP.md",
        )
    )
    for stale in (
        "SP-021 / IMPLEMENTATION_AUTHORIZED / OPEN / DRAFT",
        "SP-021 Draft",
        "SP-021 已获实现授权并处于 Draft",
        "等待独立审查且未获 Ready/Merge 授权",
        "SP-021、INT-001、\nSP-021 已",
    ):
        assert stale not in current_documents


def test_int001_post_merge_reconciliation_is_consistent() -> None:
    state = _load_state()
    arch = state["governance_tasks"]["ARCH-001"]
    sp021 = state["sp_records"]["SP-021"]
    final_status = (
        "APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / "
        "POST_MERGE_RECONCILED / ARCHIVED"
    )
    pilot_status = PILOT_001_STATUS

    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["schema_version"] == 1
    for unauthorized_root in (
        "integration_tasks",
        "integration_records",
        "current_integration_task",
        "completed_integration_tasks",
        "pilot_tasks",
        "pilot_records",
        "current_pilot",
        "route_tasks",
    ):
        assert unauthorized_root not in state
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert arch["follow_up_tasks"]["INT-001"] == final_status
    assert sp021["follow_up_tasks"]["INT-001"] == final_status
    assert arch["follow_up_tasks"]["PILOT-001"] == pilot_status
    assert sp021["follow_up_tasks"]["PILOT-001"] == pilot_status
    assert arch["follow_up_tasks"]["REL-036"] == "NOT_STARTED / NOT_APPROVED"
    assert sp021["follow_up_tasks"]["REL-036"] == "NOT_STARTED / NOT_APPROVED"

    quality = state["quality_candidates"]
    assert quality["QUALITY-003"]["authorized"] is False
    assert "REAL_PROVIDER_ONLY" in quality["QUALITY-003"]["status"]
    assert quality["QUALITY-004"]["authorized"] is True
    assert "PILOT_SAFETY_BLOCKER_CLEARED" in quality["QUALITY-004"]["status"]
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"

    paths = {
        "implementation": ROOT
        / "docs/project/INT-001-SHELL-NEUTRAL-TRUSTED-INTERACTION-ADAPTER.md",
        "projection": ROOT / "docs/project/INT-001-HERMES-MCP-PROJECTION.md",
        "acceptance": ROOT
        / "docs/acceptance/INT-001-shell-neutral-trusted-interaction-adapter.md",
        "reconciliation": ROOT
        / "docs/project/INT-001-POST-MERGE-RECONCILIATION.md",
    }
    assert all(path.is_file() for path in paths.values())
    text = {
        name: path.read_text(encoding="utf-8-sig")
        for name, path in paths.items()
    }
    reconciliation = text["reconciliation"]
    for marker in (
        "#70",
        "696fc66e26d7a69fc2fb2a0dc67f33f7400f2912",
        "49d77b6bd6bde3fe39eaecd5a7f8aa5b66249356",
        "Parent Count | `1`",
        "c3c71c7934e50725e4a82ef745245fcdb502811c",
        "2026-08-09T16:50:10Z",
        "31324821391 / SUCCESS",
        "1775 passed / 6 skipped / 26 warnings",
        "10 passed / 5 skipped",
        "NO EVIDENCE OF EXECUTION",
        "ACC-INT-001 A-Q:",
        "Modify policy/risk drift",
        "Recovery policy gate",
        "`final` terminality semantics",
        "Runtime acceptance evidence completeness",
        "Trusted adapter/transport provenance",
        "RESOLVED / INDEPENDENTLY_VERIFIED",
        "SELF_CLOSING",
        "NO_RECURSIVE_RECONCILIATION",
        "INT-001B",
        "DO_NOT_CREATE",
        "99de47895b967bc41c3b1dcb3d2caaa630fcd4de",
        "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
    ):
        assert marker in reconciliation
    assert reconciliation.count("RESOLVED / INDEPENDENTLY_VERIFIED") == 5

    combined = "\n".join(text.values())
    for marker in (
        "trusted-interaction/v1",
        "PASSED / FINAL / INDEPENDENT_REVIEW_PASSED",
        "696fc66e26d7a69fc2fb2a0dc67f33f7400f2912",
        "c3c71c7934e50725e4a82ef745245fcdb502811c",
        "31324821391 / SUCCESS",
        "RESOLVED / INDEPENDENTLY_VERIFIED",
        "SELF_CLOSING",
        "NO_RECURSIVE_RECONCILIATION",
        "INT-001B",
        "DO_NOT_CREATE",
        "99de47895b967bc41c3b1dcb3d2caaa630fcd4de",
        "60fc299c4f4fd1ba22fc4a00d1490f3b2b893503",
    ):
        assert marker in combined

    current_documents = "\n".join(
        (ROOT / path).read_text(encoding="utf-8-sig")
        for path in (
            "README.md",
            "docs/project/PROJECT_BRAIN.md",
            "docs/project/PROJECT_STATUS.md",
            "docs/project/PROJECT_HEALTH.md",
            "docs/project/ROADMAP.md",
        )
    )
    for stale in (
        "当前工作：INT-001",
        "INT-001 / OPEN / DRAFT",
        "INT-001 已获实现授权",
        "INT-001 / PENDING_INDEPENDENT_REVIEW",
        "INT-001 / NOT_READY",
        "INT-001 / NOT_MERGE_AUTHORIZED",
    ):
        assert stale not in current_documents

    inventory = (ROOT / "docs/project/MARKDOWN_INVENTORY.md").read_text(
        encoding="utf-8-sig"
    )
    for path in (
        "docs/project/INT-001-SHELL-NEUTRAL-TRUSTED-INTERACTION-ADAPTER.md",
        "docs/project/INT-001-HERMES-MCP-PROJECTION.md",
        "docs/acceptance/INT-001-shell-neutral-trusted-interaction-adapter.md",
        "docs/project/INT-001-POST-MERGE-RECONCILIATION.md",
    ):
        assert path in inventory


def test_pilot001_planning_baseline_is_scoped_and_implementation_is_not_authorized() -> None:
    state = _load_state()
    arch = state["governance_tasks"]["ARCH-001"]
    sp021 = state["sp_records"]["SP-021"]
    pilot_status = PILOT_001_STATUS

    assert state["schema_version"] == 1
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"
    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert (
        state["development_status"]
        == "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert arch["follow_up_tasks"]["PILOT-001"] == pilot_status
    assert sp021["follow_up_tasks"]["PILOT-001"] == pilot_status
    assert arch["follow_up_tasks"]["REL-036"] == "NOT_STARTED / NOT_APPROVED"
    assert sp021["follow_up_tasks"]["REL-036"] == "NOT_STARTED / NOT_APPROVED"

    for unauthorized_root in (
        "pilot_tasks",
        "pilot_records",
        "current_pilot",
        "integration_tasks",
        "integration_records",
    ):
        assert unauthorized_root not in state

    quality = state["quality_candidates"]
    assert quality["QUALITY-003"]["status"] == (
        "CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / "
        "NOT_STARTED / NOT_AUTHORIZED"
    )
    assert quality["QUALITY-003"]["authorized"] is False
    assert quality["QUALITY-004"]["status"] == (
        "RESOLVED / IMPLEMENTED / FINAL_INDEPENDENT_REVIEW_PASSED / "
        "REAL_PROVIDER_ISOLATION_GUARD_ESTABLISHED / "
        "PILOT_SAFETY_BLOCKER_CLEARED"
    )
    assert quality["QUALITY-004"]["authorized"] is True

    plan_path = (
        ROOT / "docs/project/PILOT-001-WECOM-OWNER-TRUSTED-TASK-CAPTURE.md"
    )
    acceptance_path = ROOT / "docs/acceptance/PILOT-001-wecom-owner-pilot.md"
    assert plan_path.is_file()
    assert acceptance_path.is_file()
    plan = plan_path.read_text(encoding="utf-8-sig")
    acceptance = acceptance_path.read_text(encoding="utf-8-sig")
    combined = f"{plan}\n{acceptance}"
    for marker in (
        "PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING",
        "NOT_PRODUCTION_IDENTITY_AUTHENTICATION",
        "user_task.create",
        "PilotOwnerBindingResolver",
        "PilotUserTaskExecutionPort",
        "PilotUserTaskVerificationPort",
        "PilotUserTaskCanonicalCommitAuthority",
        "PilotInteractionCoordinator",
        "Deterministic UserTask Identity",
        "Real Integration Evidence",
        "Manual Owner Evidence",
        "Restart Evidence",
        "Negative Evidence",
        "RFC / ADR Required: NO",
        "PLANNING_BASELINE_APPROVED",
        "FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED",
        "IMPLEMENTATION_NOT_AUTHORIZED",
        "REQUIRES_SEPARATE_IMPLEMENTATION_AUTHORIZATION",
        "REAL_PILOT_NOT_STARTED",
        "PHASE_0_NOT_AUTHORIZED",
        "0 EXECUTED",
    ):
        assert marker in combined

    for marker in (
        "Fresh Owner Ingress Evidence",
        "Static Pilot Owner Binding",
        "Fresh Owner Confirmation Evidence",
        "Same Inbound Event / Same Agent Turn Auto-Confirm → DENIED",
        "Phase 0 Coordinator: DISABLED / UNBOUND",
        "Phase 1 Coordinator: DISABLED / UNBOUND",
        "Phase-specific Hermes Tool Exposure",
        "dm_policy: allowlist",
        "group_policy: disabled",
        "VerificationPort 不负责完整",
        "Preview 参数 commit 比较",
        "CanonicalCommitRequest.normalized_parameters",
        "outcome=COMMITTED",
        "ZERO BUSINESS SIDE EFFECT",
        "STOPPED_PENDING_INGRESS_BRIDGE_DESIGN",
    ):
        assert marker in combined

    for marker in (
        "P0-10",
        "P0-11",
        "P0-12",
        "P0-13",
        "P0-14",
        "P0-15",
        "0 UserTask created / 0 target business mutation",
        "preview、status、view",
        "dm_policy=allowlist",
        "group_policy=disabled",
    ):
        assert marker in acceptance

    assert "不计划修改 `VerificationRequest`" in plan
    assert "`core/interaction/models.py` 或 `core/interaction/service.py`" in plan
    assert "Message A != Message B" in combined
    current_documents = "\n".join(
        (ROOT / path).read_text(encoding="utf-8-sig")
        for path in (
            "README.md",
            "CHANGELOG.md",
            "docs/project/PROJECT_BRAIN.md",
            "docs/project/PROJECT_HEALTH.md",
            "docs/project/PROJECT_STATUS.md",
            "docs/project/ROADMAP.md",
            "docs/project/VERSION_MATRIX.md",
        )
    )
    assert "FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED" in current_documents
    assert "REAL_PILOT_NOT_STARTED" in current_documents
    for stale_current_truth in (
        "PILOT-001-PLANNING",
        "PLANNING_AUTHORIZED / OPEN / DRAFT / PENDING_INDEPENDENT_REVIEW",
        "DESIGN_BASELINE_IN_PROGRESS",
    ):
        assert stale_current_truth not in current_documents
    for forbidden_domain in (
        "QuoteRequest",
        "Pricing Engine",
        "Enterprise IAM 实现",
    ):
        assert forbidden_domain not in combined


def test_quality004_real_provider_isolation_guard_has_durable_approval() -> None:
    state = _load_state()
    quality003 = state["quality_candidates"]["QUALITY-003"]
    quality004 = state["quality_candidates"]["QUALITY-004"]

    assert state["schema_version"] == 1
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    assert state["development_status"] == (
        "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert state["latest_merged_sp"] == "SP-021"
    assert state["latest_completed_sp"] == "SP-021"
    assert state["current_version"] == "0.35.0"
    assert state["version"] == "v0.35.0"
    assert quality004 == {
        "name": "Real-Provider Credential Isolation Guard",
        "status": (
            "RESOLVED / IMPLEMENTED / FINAL_INDEPENDENT_REVIEW_PASSED / "
            "REAL_PROVIDER_ISOLATION_GUARD_ESTABLISHED / "
            "PILOT_SAFETY_BLOCKER_CLEARED"
        ),
        "classification": "SAFETY_FIX / TEST_EXECUTION_ISOLATION / PILOT_BLOCKER",
        "base_commit": "0f1fca015248bbf2c5f87175d887b770e68dc07c",
        "branch": "fix/quality-004-real-provider-isolation-guard",
        "observation": (
            "Ordinary pytest could import tests/real, where python-dotenv reloaded "
            "local credentials and credential presence implicitly enabled "
            "real-provider execution"
        ),
        "required_guard": (
            "--run-real-provider AND AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1"
        ),
        "approved_head": "32816b750907cc03bd5c7c61bd1fb1ebbaf77d5b",
        "independent_review_status": "FINAL_REVIEW_PASSED",
        "blocking_status": "CLEARED_FOR_P0_E_REVALIDATION",
        "real_provider_called_during_implementation": False,
        "authorized": True,
    }
    assert quality003["status"] == (
        "CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / "
        "NOT_STARTED / NOT_AUTHORIZED"
    )
    assert quality003["authorized"] is False
    assert state["governance_tasks"]["ARCH-001"]["follow_up_tasks"]["REL-036"] == (
        "NOT_STARTED / NOT_APPROVED"
    )
    for unauthorized_root in (
        "quality_tasks",
        "quality_records",
        "current_quality_task",
        "pilot_tasks",
        "pilot_records",
        "current_pilot",
    ):
        assert unauthorized_root not in state

    guard = (ROOT / "conftest.py").read_text(encoding="utf-8-sig")
    assert "--run-real-provider" in guard
    assert "AI_LAB_ALLOW_REAL_PROVIDER_TESTS" in guard
    assert "pytest_ignore_collect" in guard

    documentation = "\n".join(
        (ROOT / path).read_text(encoding="utf-8-sig")
        for path in (
            "README.md",
            "CHANGELOG.md",
            "docs/project/KNOWN_LIMITATIONS.md",
            "docs/project/PROJECT_STATUS.md",
        )
    )
    assert "P0_E_ENVIRONMENT_READY" in documentation
    assert "P0_R_FINAL_INDEPENDENT_REVIEW_PASSED" in documentation
    assert "PILOT_SAFETY_BLOCKER_CLEARED" in documentation
    assert "不是 WeCom/MCP compatibility failure" in documentation


def test_pilot001_p0r_preview_and_fresh_ingress_stop_state_are_durable() -> None:
    state = _load_state()
    pilot_status = state["governance_tasks"]["ARCH-001"]["follow_up_tasks"][
        "PILOT-001"
    ]
    evidence_path = (
        ROOT / "docs/acceptance/PILOT-001-phase0-hermes-wecom-discovery.md"
    )
    evidence = evidence_path.read_text(encoding="utf-8-sig")

    assert state["schema_version"] == 1
    assert state["current_version"] == "0.35.0"
    assert state["current_work"] is None
    assert state["development_status"] == (
        "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    for marker in (
        "P0_E_ENVIRONMENT_READY",
        "P0_R_IMPLEMENTATION_AUTHORIZED",
        "P0_R_IMPLEMENTED",
        "P0_R_FINAL_INDEPENDENT_REVIEW_PASSED",
        "PREVIEW_AUTHORITY_ESTABLISHED",
        "FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED",
        "PHASE_0_STOPPED_PENDING_INGRESS_BRIDGE_DESIGN",
        "PHASE_1_NOT_AUTHORIZED",
        "PHASE_2_NOT_AUTHORIZED",
        "REAL_BUSINESS_MUTATION_NOT_AUTHORIZED",
    ):
        assert marker in pilot_status
        assert marker in evidence
    assert (
        state["sp_records"]["SP-021"]["follow_up_tasks"]["PILOT-001"]
        == pilot_status
    )
    assert evidence_path.is_file()
    for marker in (
        "NOT_PRODUCTION_IDENTITY_AUTHENTICATION",
        "PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING",
        "pilot-001/user-task-create/v1",
        "NO_NEW_WECOM_EVENT=YES",
        "CONTROLLED_MCP_REPLAY=ACCEPTED",
        "UserTask Created | 0",
        "AI-Lab Real Provider Called | `NO`",
        "call_tool(tool_name, arguments=args)",
    ):
        assert marker in evidence
    assert "Owner raw WeCom ID" in evidence
    assert "QUALITY-003、REL-036" in evidence


def test_pilot001_p1a_internal_confirmation_evidence_is_durable() -> None:
    state = _load_state()
    pilot_status = state["governance_tasks"]["ARCH-001"]["follow_up_tasks"][
        "PILOT-001"
    ]
    acceptance_path = (
        ROOT
        / "docs/acceptance/PILOT-001-P1A-internal-trusted-ingress-confirmation.md"
    )
    acceptance = acceptance_path.read_text(encoding="utf-8-sig")

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
    for marker in (
        "PILOT_001_P1A_INTERNAL_CONFIRMATION_AUTHORIZED",
        "PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE",
        "INTERNAL_PILOT_TRUSTED_CONFIRMATION_PROVEN",
        "PRODUCTION_PROCESS_ISOLATION_UNRESOLVED",
        "FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED",
        "PHASE_1_FULL_NOT_AUTHORIZED",
        "PHASE_2_NOT_AUTHORIZED",
        "REAL_BUSINESS_MUTATION_NOT_AUTHORIZED",
    ):
        assert marker in pilot_status
    for marker in (
        "Message A: PASS",
        "Fresh Message B: PASS",
        "Interaction final state: AUTHORIZED / revision 3",
        "Execution: NOT_STARTED",
        "UserTask: 3 -> 3",
        "AI-Lab Real Provider: 0",
        "trusted_confirmation.validation_denied",
        "INTERNAL_PILOT_TRUSTED_CONFIRMATION_PROVEN",
        "PRE_R1_REAL_EVIDENCE / CONTRACT_IMPLEMENTATION_REVISED",
        "P1A-N",
        "P1A-O",
        "P1A-P",
        "P1A-Q",
        "operator-provisioned opaque",
        "durable issuance journal",
        "verifier projection root",
        "signing-key rotation",
        "正式 `start-gateway` 路径",
    ):
        assert marker in acceptance
    assert not (ROOT / ".hermes/plugins/platforms/wecom").exists()


def test_pilot001_ibd_approved_design_state_is_durable() -> None:
    state = _load_state()
    arch = state["governance_tasks"]["ARCH-001"]
    sp021 = state["sp_records"]["SP-021"]
    pilot_status = arch["follow_up_tasks"]["PILOT-001"]

    assert state["schema_version"] == 1
    assert state["current_work"] is None
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["next_planned_governance_item"] is None
    assert state["development_status"] == (
        "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert sp021["follow_up_tasks"]["PILOT-001"] == pilot_status
    for marker in (
        "FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED",
        "INGRESS_EVIDENCE_BRIDGE_DESIGN_APPROVED",
        "INGRESS_EVIDENCE_BRIDGE_FINAL_INDEPENDENT_REVIEW_PASSED",
        "RFC_033_ADOPTED",
        "ADR_073_ACCEPTED",
        "PILOT_001_IB_IMP_A_AUTHORIZED",
        "PILOT_001_IB_IMP_A_STOPPED_SIGNING_ORACLE_ISOLATION_FAILED",
        "PILOT_001_IB_IMP_A_FINAL_CLASSIFICATION_UNSUPPORTED",
        "PILOT_001_IB_IMP_A_FINAL_INDEPENDENT_SECURITY_REVIEW_PASSED",
        "PILOT_001_IB_IMP_A_NEGATIVE_EVIDENCE_BASELINE_APPROVED",
        "INGRESS_PROCESS_ISOLATION_UNRESOLVED",
        "BRIDGE_IMPLEMENTATION_NOT_AUTHORIZED",
        "PHASE_1_NOT_AUTHORIZED",
        "PHASE_2_NOT_AUTHORIZED",
        "REAL_BUSINESS_MUTATION_NOT_AUTHORIZED",
    ):
        assert marker in pilot_status
    assert "INGRESS_EVIDENCE_BRIDGE_DESIGN_DRAFT" not in pilot_status
    assert "PENDING_INDEPENDENT_REVIEW" not in pilot_status

    paths = {
        "design": ROOT
        / "docs/project/PILOT-001-TRUSTED-INGRESS-EVIDENCE-BRIDGE.md",
        "acceptance": ROOT
        / "docs/acceptance/PILOT-001-ingress-evidence-bridge.md",
        "rfc": ROOT / "docs/rfc/033-trusted-ingress-evidence-bridge.md",
        "adr": ROOT
        / "docs/adr/ADR-073-ai-lab-owned-ingress-evidence-consumption.md",
    }
    for path in paths.values():
        assert path.is_file()

    design = paths["design"].read_text(encoding="utf-8-sig")
    acceptance = paths["acceptance"].read_text(encoding="utf-8-sig")
    rfc = paths["rfc"].read_text(encoding="utf-8-sig")
    adr = paths["adr"].read_text(encoding="utf-8-sig")
    for marker in (
        "Recommended Architecture:",
        "Trusted Evidence Issuer:",
        "Evidence Verification Authority:",
        "Replay Ownership:",
        "Hermes Source Change:",
        "New AI-Lab Core Contract Required:",
        "MCP Contract Change Required:",
        "Implementation:\nREQUIRES_SEPARATE_AUTHORIZATION",
        "PHASE_1:\nNOT_AUTHORIZED",
    ):
        assert marker in design
    for scenario in tuple(f"IB-{letter}" for letter in "ABCDEFGHIJKLMNOPQRS"):
        assert scenario in acceptance
    assert (
        "PLANNING_BASELINE_APPROVED / "
        "FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED / NOT_EXECUTED"
        in acceptance
    )
    assert "IB-A～IB-S 均为 `DEFINED / NOT_EXECUTED`" in acceptance
    assert "7042a68c566abf4c99f5f3038b38fd90790f0bfb" in design
    for document in (design, acceptance, rfc, adr):
        for marker in (
            "evidence_version",
            "evidence_id",
            "issuer_key_id",
            "channel_account_binding_id",
            "owner_binding_id",
            "conversation_binding_id",
            "received_at",
            "event_type",
            "message_content_digest",
            "expires_at",
            "signature",
            "RFC 8785",
            "event_identity_key",
            "PRIMARY KEY (evidence_id)",
        ):
            assert marker in document
        assert "received_at" in document
        assert "issuer_key_id" in document
        assert "不参与 identity" in document
    assert "SIGNING_ORACLE_DENIED" in acceptance
    assert "DUPLICATE_EVENT_STABLE_IDENTITY" in acceptance
    assert "PREVIEW_BEFORE_EVENT_CAUSALITY" in acceptance
    assert "CHANNEL_EVENT_ID_FALLBACK_DENIED" in acceptance
    assert "trusted_ingress.channel_event_id_unavailable" in acceptance
    for document in (design, acceptance, rfc, adr):
        for marker in (
            "body.msgid",
            "headers.req_id",
            "raw_wecom_msgid",
            "preview_confirmation_challenge",
            "accepted_at",
            "不单独证明",
        ):
            assert marker in document
        assert "MessageEvent.message_id" in document
        assert "owner_binding_id" in document
        assert "conversation_binding_id" in document
    assert "preview_confirmation_code" not in design
    assert "preview_confirmation_code" not in rfc
    assert "replay_key`。`evidence_id`" not in rfc
    assert "`replay_key`。`evidence_id`" not in design
    assert "**状态**：Adopted" in rfc
    assert "RFC-033:\nADOPTED" in rfc
    assert "**状态**：Accepted" in adr
    assert "ADR-073:\nACCEPTED" in adr
    for document in (design, acceptance, rfc, adr):
        assert "PENDING_INDEPENDENT_REVIEW" not in document
    assert "BRIDGE_IMPLEMENTATION:\nNOT_AUTHORIZED" in rfc
    assert "BRIDGE_IMPLEMENTATION:\nNOT_AUTHORIZED" in adr


def test_pilot001_ib_imp_a_stopped_security_spike_is_durable() -> None:
    state = _load_state()
    arch = state["governance_tasks"]["ARCH-001"]
    sp021 = state["sp_records"]["SP-021"]
    pilot_status = arch["follow_up_tasks"]["PILOT-001"]
    evidence_path = (
        ROOT
        / "docs/acceptance/PILOT-001-IB-IMP-A-hermes-capability-spike.md"
    )
    live_plugin_path = ROOT / ".hermes/plugins/platforms/wecom"
    fixture_path = (
        ROOT
        / "tests/spike/pilot_001_ingress_capability/fixtures/"
        "hermes_project_plugin/platforms/wecom"
    )

    assert state["schema_version"] == 1
    assert state["current_work"] is None
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["development_status"] == (
        "pilot_001_phase0_stopped_pending_ingress_process_isolation_resolution"
    )
    assert sp021["follow_up_tasks"]["PILOT-001"] == pilot_status
    for marker in (
        "PILOT_001_IB_IMP_A_AUTHORIZED",
        "PILOT_001_IB_IMP_A_STOPPED_SIGNING_ORACLE_ISOLATION_FAILED",
        "PILOT_001_IB_IMP_A_FINAL_CLASSIFICATION_UNSUPPORTED",
        "PILOT_001_IB_IMP_A_FINAL_INDEPENDENT_SECURITY_REVIEW_PASSED",
        "PILOT_001_IB_IMP_A_NEGATIVE_EVIDENCE_BASELINE_APPROVED",
        "INGRESS_PROCESS_ISOLATION_UNRESOLVED",
        "FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED",
        "BRIDGE_IMPLEMENTATION_NOT_AUTHORIZED",
        "PHASE_1_NOT_AUTHORIZED",
        "PHASE_2_NOT_AUTHORIZED",
        "REAL_BUSINESS_MUTATION_NOT_AUTHORIZED",
    ):
        assert marker in pilot_status

    assert evidence_path.is_file()
    assert not live_plugin_path.exists()
    assert fixture_path.is_dir()
    fixture_manifest = (fixture_path / "plugin.yaml").read_text(encoding="utf-8")
    assert "PILOT_SPIKE_ONLY" in fixture_manifest
    assert "NOT_PRODUCT_RUNTIME" in fixture_manifest
    evidence = evidence_path.read_text(encoding="utf-8-sig")
    for marker in (
        "STOPPED_SIGNING_ORACLE_ISOLATION_FAILED",
        "UNSUPPORTED",
        "pidfd_getfd",
        "duplicated=true / invoked=true",
        "CHANNEL_EVENT_ID_CONTRACT_UNPROVEN",
        "CURRENT_PILOT_DEPLOYMENT:\nUNSUPPORTED",
        "DESIGN_BASELINE_RETAINED /\nPROCESS_ISOLATION_UNRESOLVED",
        "FINAL_INDEPENDENT_SECURITY_REVIEW:\nPASSED",
        "NEGATIVE_EVIDENCE_BASELINE:\nAPPROVED",
        "SPIKE-M `FAILED_PLUGIN_NOT_LIVE_DISCOVERABLE` | PASS",
        "业务 mutation：`0`",
        "Real Provider：`0`",
        "BRIDGE_IMPLEMENTATION:\nNOT_AUTHORIZED",
        "PHASE_1:\nNOT_AUTHORIZED",
        "PHASE_2:\nNOT_AUTHORIZED",
    ):
        assert marker in evidence


def test_sp022_planning_contract_is_complete_and_not_authorized() -> None:
    paths = {
        "plan": ROOT / "docs/project/SP-022-V037-QUOTE-REQUEST-PLANNING.md",
        "rfc": ROOT / "docs/rfc/034-quote-request-trusted-write-contract.md",
        "ownership": ROOT
        / "docs/adr/ADR-074-quote-follow-up-next-action-ownership.md",
        "reconciliation": ROOT
        / "docs/adr/ADR-075-inbox-to-quote-request-reconciliation.md",
        "acceptance": ROOT / "docs/acceptance/SP-022-quote-request.md",
    }
    documents = {
        name: path.read_text(encoding="utf-8-sig")
        for name, path in paths.items()
    }

    assert (
        "PLANNING_BASELINE_PROPOSED / PENDING_INDEPENDENT_PLANNING_REVIEW / "
        "IMPLEMENTATION_NOT_AUTHORIZED / ACC_022_NOT_EXECUTED"
        in documents["plan"]
    )
    assert "DRAFT / NOT_ADOPTED" in documents["rfc"]
    assert "PROPOSED / NOT_ACCEPTED" in documents["ownership"]
    assert "PROPOSED / NOT_ACCEPTED" in documents["reconciliation"]
    assert "PLANNING_BASELINE / 0_EXECUTED / NOT_PASSED" in documents["acceptance"]
    assert documents["acceptance"].count("PLANNED / NOT_EXECUTED") >= 36

    for marker in (
        "quote_request_id",
        "WorkspaceKey",
        "expected_revision",
        "quote.revision_conflict",
        "quote.idempotency_conflict",
        "quote.invalid_transition",
        "quote.persistence_failed",
        "quote.projection_failed",
        "Quote canonical mutation proof",
        "canonical read-back",
    ):
        assert marker in documents["rfc"]

    assert "Waiting-For canonical reference/projection" in documents["ownership"]
    assert "Daily Review 只消费 canonical read model" in documents["ownership"]
    assert "CLAIMED -> TARGET_CREATED -> TARGET_VERIFIED -> TARGET_LINKED -> COMPLETED" in documents["reconciliation"]
    assert "不依赖跨数据库原子事务" in documents["reconciliation"]
    assert "SEPARATE_AUTHORIZATION_REQUIRED" in documents["plan"]
    assert "NOT_PART_OF_INITIAL_IMPLEMENTATION_AUTHORIZATION" in documents["plan"]

    failure_categories = {
        "quote.workspace_mismatch": ErrorCategory.PERMISSION_DENIED,
        "quote.not_found": ErrorCategory.NOT_FOUND,
        "quote.revision_conflict": ErrorCategory.CONFLICT,
        "quote.idempotency_conflict": ErrorCategory.CONFLICT,
        "quote.invalid_transition": ErrorCategory.VALIDATION,
        "quote.validation_failed": ErrorCategory.VALIDATION,
        "quote.persistence_failed": ErrorCategory.PERSISTENCE_FAILURE,
        "quote.projection_failed": ErrorCategory.DEPENDENCY_FAILURE,
    }
    for code, category in failure_categories.items():
        assert f"`{code}` | {category.value} |" in documents["rfc"]

    assert "同 key 异 payload/operation" not in documents["rfc"]
    assert (
        "同一完整 WorkspaceKey、同 operation、同 idempotency key、不同 normalized payload"
        in documents["rfc"]
    )
    assert "跨 workspace linkage 一律返回 `quote.workspace_mismatch`" not in documents["ownership"]
    assert (
        "foreign ID 与 absent ID 一律返回不可区分的 `quote.not_found / not_found`"
        in documents["ownership"]
    )
    assert "不重复 Audit" not in documents["acceptance"]
    assert "不重复 QuoteAuditRecord" in documents["acceptance"]
    assert "Audit correlation 与 Verified Result" not in documents["reconciliation"]
    assert "匹配的 QuoteAuditRecord" in documents["reconciliation"]
    assert "QuoteMutationResult" in documents["reconciliation"]
    assert "Slice B 不构造 Interaction VerifiedResult/AuditEvidence" in documents["reconciliation"]

    for marker in (
        "foreign ID 与 absent ID",
        "禁止跨 workspace fallback lookup",
        "零存在性泄露",
        "full WorkspaceKey + operation + idempotency_key",
        "不同 operation、同 key 按 operation namespace 相互独立",
        "不同 workspace 使用相同 key 字符串也相互独立",
        "QuoteMutationResult",
        "QuoteAuditRecord",
        "同一个 `quotes.db` transaction",
        "真实 Interaction/Execution identity",
        "禁止 placeholder ID",
        "cus_<32 lowercase hex>",
        "con_<32 lowercase hex>",
        "不支持 hard delete",
    ):
        assert marker in documents["rfc"] + documents["ownership"]

    for marker in (
        "absent ID 与 foreign-workspace ID",
        "无跨 workspace fallback lookup",
        "同 workspace 不同 operation",
        "不同 workspace 的相同 key",
        "Customer create/read/update",
        "Contact create/read/update",
        "hard delete 不受支持",
    ):
        assert marker in documents["acceptance"]

    state = _load_state()
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["current_work"] is None
