from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "project_state.json"


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

    assert runtime_version == "0.34.0"
    assert state["current_version"] == runtime_version
    assert state["version"] == f"v{runtime_version}"
    assert state["release_status"]["current_version"] == runtime_version


def test_human_facing_current_state_markers_match_project_state() -> None:
    state = _load_state()
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
    brain = (ROOT / "docs/project/PROJECT_BRAIN.md").read_text(encoding="utf-8-sig")

    assert f"v{state['current_version']} Alpha / Release Authorized" in readme
    assert f"Product Version: {state['version']}" in brain
    assert f"Last Completed SP: {state['latest_completed_sp']}" in brain
    assert f"Current SP: {state['current_sp']}" in brain
    assert f"Current Governance Task: {state['current_governance_task']}" in brain
    assert f"Next Candidate SP: {state['next_candidate_sp']}" in brain
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

    assert state["current_sp"] == "SP-018"
    assert state["current_governance_task"] is None
    assert _sp_number(state["next_candidate_sp"]) > _sp_number(
        state["latest_completed_sp"]
    )


def test_sp015_release_baseline_is_archived_while_sp017_is_latest_work() -> None:
    state = _load_state()
    sp015 = state["sp_records"]["SP-015"]

    assert state["latest_merged_sp"] == "SP-017"
    assert state["latest_completed_sp"] == "SP-017"
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
    assert state["current_sp"] == "SP-018"
    assert state["current_governance_task"] is None
    assert state["development_status"] == (
        "sp_018_implemented_on_draft_head_automated_verification_passed"
    )
    assert state["next_candidate_sp"] == "SP-019"
    assert state["next_candidate_name"] == "Daily Review & Follow-up Brief"
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
    assert (
        "> Next Candidate Direction: Daily Review & Follow-up Brief"
        in text["brain"]
    )
    assert f"> SP-015A Status: {sp015a_status}" in text["brain"]
    assert f"> SP-015R Status: {sp015r_status}" in text["brain"]
    assert "Last Completed SP: SP-017" in text["brain"]
    assert "Current SP: SP-018" in text["brain"]
    assert "ACC-016 Status: PASSED / FINAL" in text["brain"]
    assert "ACC-017 Status: PASSED / FINAL" in text["brain"]
    assert "Current governance task | None" in text["health"]
    assert "Alpha / RELEASE_AUTHORIZED" in text["health"]
    assert "**Authorization:** Release Authorized" in text["version_matrix"]
    assert (
        "SP-015, SP-015A and SP-015R archived; SP-016 remains candidate only"
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
        "External publication verification: GitHub Tag and GitHub Release are "
        "authoritative."
    ) in text["release_checklist"]
    assert "Final publication commit prepared" in text["release_checklist"]
    assert "- [ ] SP-015R merged" not in text["release_checklist"]
    assert "授权 Tag 为 `v0.34.0`" in text["readme"]
    assert "Pre-release" in text["readme"]
    assert "GitHub Tags and GitHub Releases" in text["readme"]
    assert "授权 Tag：`v0.34.0`" in text["status"]
    assert "GitHub Release 类型：Pre-release" in text["status"]
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
        "| SP-017 | Follow-up Interaction & Capture Closure —",
        "| SP-018 | Work Log Query Boundary & Context Closure |",
        "| SP-019 | Daily Review & Follow-up Brief |",
    )
    positions = [roadmap.index(row) for row in roadmap_rows]
    assert positions == sorted(positions)
    assert (
        "| SP-017 | Follow-up Interaction & Capture Closure — Deterministic "
        "Waiting-For interaction, Inbox capture confirmation, and durable "
        "Inbox-to-Waiting-For conversion | COMPLETED / ARCHIVED |"
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
        "current_version": "0.34.0",
        "release_stage": "alpha",
        "release_authorization": "APPROVED",
        "publication_authority": "GitHub Tags and GitHub Releases",
        "authorized_tag": "v0.34.0",
        "github_release_type": "prerelease",
        "maturity": "Alpha / local-first / single-user-oriented",
        "binary_assets": "not published",
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

    assert state["current_sp"] == "SP-018"
    assert state["current_governance_task"] is None
    assert state["latest_merged_sp"] == "SP-017"
    assert state["latest_completed_sp"] == "SP-017"
    assert state["next_candidate_sp"] == "SP-019"
    assert state["next_candidate_name"] == "Daily Review & Follow-up Brief"
    assert state["development_status"] == (
        "sp_018_implemented_on_draft_head_automated_verification_passed"
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
    assert "SP-019" not in records

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
        "| SP-017 | Follow-up Interaction & Capture Closure —",
        "| SP-018 | Work Log Query Boundary & Context Closure |",
        "| SP-019 | Daily Review & Follow-up Brief |",
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
        "SP-017 Status: APPROVED / MERGED / ACCEPTED / RECONCILED / ARCHIVED",
        "Current SP: SP-018",
        "RFC-026 Adopted",
        "ACC-017 Status: PASSED / FINAL",
        "| SP-018 | Work Log Query Boundary & Context Closure | "
        "IMPLEMENTED_ON_DRAFT_HEAD / AUTOMATED_VERIFICATION_PASSED / "
        "MANUAL_ACCEPTANCE_NOT_EXECUTED / NOT_MERGED |",
        "| SP-019 | Daily Review & Follow-up Brief | "
        "CANDIDATE / NOT_APPROVED / NOT_STARTED |",
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


def test_sp018_is_implemented_on_draft_without_manual_acceptance() -> None:
    state = _load_state()
    records = state["sp_records"]
    sp018 = records["SP-018"]
    acc018 = state["acceptance_records"]["ACC-018"]

    assert state["latest_merged_sp"] == "SP-017"
    assert state["latest_completed_sp"] == "SP-017"
    assert state["current_sp"] == "SP-018"
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] == "SP-019"
    assert state["next_candidate_name"] == "Daily Review & Follow-up Brief"
    assert state["current_work"] is None
    assert "next_action" not in state

    assert sp018["name"] == "Work Log Query Boundary & Context Closure"
    assert sp018["status"] == (
        "APPROVED_FOR_IMPLEMENTATION / IMPLEMENTED_ON_DRAFT_HEAD / "
        "AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_NOT_EXECUTED / "
        "NOT_MERGED"
    )
    assert sp018["planning_baseline_defined"] is True
    assert sp018["approved"] is True
    assert sp018["implementation_started"] is True
    assert sp018["implementation_complete"] is True
    assert sp018["manual_acceptance_status"] == "NOT_EXECUTED"
    assert sp018["planning_pr"] == 45
    assert sp018["planning_head"] == "e485c99d9734a43665c0c891e886e91b59c577d6"
    assert sp018["planning_merge_commit"] == (
        "ee06f6a20004bdbf24fc94c8420c18cf1a3d45b3"
    )
    assert sp018["target_version"] == "0.35.0"
    assert sp018["rfc"] == "RFC-027"
    assert sp018["adrs"] == ["ADR-058", "ADR-059", "ADR-060"]
    assert {
        "feature_pr",
        "approved_head",
        "draft_pr",
        "github_check_status",
        "merge_commit",
        "merged",
        "accepted",
        "archived",
        "reconciled",
    }.isdisjoint(sp018)

    assert acc018["status"] == "IMPLEMENTATION_DRAFT / NOT_EXECUTED"
    assert acc018["manual_acceptance"] is False
    assert acc018["scenarios"] == {
        letter: "NOT_EXECUTED" for letter in "ABCDEFGHIJKLMNO"
    }

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
    assert "ACC-018 人工验收尚未执行" in rfc
    assert all(
        "Status: Accepted" in content for content in (adr058, adr059, adr060)
    )
    assert "NOT_EXECUTED" in acceptance
    assert all(f"ACC-018-{letter}" in acceptance for letter in "ABCDEFGHIJKLMNO")
    assert (
        "| RFC-027 | Work Log Query Boundary and Context Closure | "
        "Adopted |"
    ) in decision_index
    assert all(
        f"| ADR-{number} |" in decision_index for number in ("058", "059", "060")
    )
    assert (
        "| SP-018 | Work Log Query Boundary & Context Closure | "
        "IMPLEMENTED_ON_DRAFT_HEAD / AUTOMATED_VERIFICATION_PASSED / "
        "MANUAL_ACCEPTANCE_NOT_EXECUTED / NOT_MERGED |"
    ) in roadmap
    assert (
        "| SP-019 | Daily Review & Follow-up Brief | "
        "CANDIDATE / NOT_APPROVED / NOT_STARTED |"
    ) in roadmap
    assert "SP-018 Draft implementation facts" in brain
    assert "不会创建 `work_logs.db`" in brain
    assert "SP-019 必须等待 SP-018" in brain
    assert "Legacy Work Log Projection Table" in rfc
    assert "普通随机 Memory ID 仍不作为公开 alias" in rfc
    assert "历史 `inbox_wl_<合法历史格式>` 是唯一受限兼容 lookup alias" in rfc
    assert "返回同一对象的 canonical `wl_legacy_" in rfc
    assert "SP-018 没有业务结果 candidate cap" in rfc
    assert "这些阈值只产生观测信号" in rfc
    assert "Ordinary random Memory IDs" in adr059
    assert "the only restricted compatibility lookup alias" in adr059
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
    assert "状态：IMPLEMENTATION_DRAFT / NOT_EXECUTED" in (
        acceptance
    )

    planning_files = (
        rfc,
        adr058,
        adr059,
        adr060,
        acceptance,
        decision_index,
        roadmap,
        brain,
    )
    forbidden_acceptance_claims = (
        "ACC-018 A～O：PASSED",
        "SP-018 Status: MANUAL_ACCEPTANCE_PASSED",
        "SP-018 Status: IN_PROGRESS",
    )
    assert all(
        marker not in content
        for marker in forbidden_acceptance_claims
        for content in planning_files
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
    }
    text = {
        name: path.read_text(encoding="utf-8-sig")
        for name, path in paths.items()
    }
    assert "self._work_logs.create(" in text["assistant"]
    assert "self._work_logs.list(" in text["assistant"]
    assert "self._work_logs.get(" in text["assistant"]
    assert "self._work_logs.create_from_inbox(" in text["inbox"]
    assert "self._work_logs.list(" in text["agenda"]
    assert "system.work_log_service" in text["api"]
    assert "execute_work_log_operation" in text["cli"]
    assert "execute_work_log_operation" in text["legacy_cli"]
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
