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

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] is None


def test_sp015_release_baseline_is_archived_while_sp019_is_latest_work() -> None:
    state = _load_state()
    sp015 = state["sp_records"]["SP-015"]

    assert state["latest_merged_sp"] == "SP-019"
    assert state["latest_completed_sp"] == "SP-019"
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
    assert state["development_status"] == "sp_019_completed_reconciled_archived"
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
    assert "> Next Candidate Direction: None" in text["brain"]
    assert f"> SP-015A Status: {sp015a_status}" in text["brain"]
    assert f"> SP-015R Status: {sp015r_status}" in text["brain"]
    assert "Last Completed SP: SP-019" in text["brain"]
    assert "Current SP: None" in text["brain"]
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
        "| SP-019 | Daily Review Read Model & Deterministic Follow-up View |",
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

    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["latest_merged_sp"] == "SP-019"
    assert state["latest_completed_sp"] == "SP-019"
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["development_status"] == "sp_019_completed_reconciled_archived"
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
        "| SP-017 | Follow-up Interaction & Capture Closure —",
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
        "SP-017 Status: APPROVED / MERGED / ACCEPTED / RECONCILED / ARCHIVED",
        "Current SP: None",
        "RFC-026 Adopted",
        "ACC-017 Status: PASSED / FINAL",
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

    assert state["latest_merged_sp"] == "SP-019"
    assert state["latest_completed_sp"] == "SP-019"
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
    assert "Feature PR：#46" in acceptance
    assert (
        "Approved Head：`e941cadc783a6ac8a4bd3c75b55adf77e0a651a3`"
        in acceptance
    )
    assert (
        "Feature Merge Commit：`83ecb557fedd1d898712afc59ad13b3e0a684413`"
        in acceptance
    )
    assert "SP-018A Reconciliation PR：#47（MERGED）" in acceptance
    assert "4e0d730a8bfdefa6277c7526a028e7247d7ddc43" in acceptance
    assert "30198434517" in acceptance
    assert "PR Quality Gate Run：`30195401115`" in acceptance
    assert "Post-Merge main Quality Gate Run：`30196719409`" in acceptance
    assert "Independent Review：`APPROVED`" in acceptance
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
        "NOT_MERGED",
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

    assert state["latest_merged_sp"] == "SP-019"
    assert state["latest_completed_sp"] == "SP-019"
    assert state["current_sp"] is None
    assert state["current_governance_task"] is None
    assert state["next_candidate_sp"] is None
    assert state["next_candidate_name"] is None
    assert state["current_version"] == "0.34.0"
    assert state["version"] == "v0.34.0"
    assert state["development_status"] == "sp_019_completed_reconciled_archived"
    assert state["current_work"] is None
    assert state["release_status"]["authorized_tag"] == "v0.34.0"
    assert state["release_status"]["current_version"] == "0.34.0"
    assert "SP-020" not in state["sp_records"]
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
        "> Last Completed SP: SP-019\n"
        "> Current SP: None\n"
        "> Current Governance Task: None\n"
        "> Next Candidate SP: None"
    ) in brain
    assert (
        "> SP-019 Status: APPROVED / MERGED / POST_MERGE_VERIFIED / "
        "MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED"
    ) in brain
    assert (
        "> SP-019 Planning Merge Baseline: "
        "`e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / "
        "Quality Gate run `30205853257` / SUCCESS"
    ) in brain
    assert "> Current main:" not in brain
    assert "Latest Merged SP 为 SP-019" in project_status
    assert "Latest Completed SP 为 SP-019" in project_status
    assert "Current Product SP 为 None" in project_status
    assert "Current Governance Task 为 None" in project_status
    assert "Next Candidate SP 为 None" in project_status
    assert (
        "SP-019 Feature PR #51 已由 Acceptance Evidence Head "
        "`420da28664914fda8ccbecadf90947380ec43473` Squash Merge 为 main "
        "`a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`"
    ) in project_status
    assert (
        "| Current product SP | None |\n"
        "| Current governance task | None |\n"
        "| Next candidate | None |"
    ) in project_health
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
        "GET /brief\n"
        "CEO Assistant：今日简报 / 昨日简报"
    ) in readme
    assert (
        "Daily Review 只支持 `today` / `yesterday`，不持久化 Review "
        "snapshot，不支持任意历史日期，不调用 LLM、不主动推送，且没有 "
        "Daily Review CLI。"
    ) in readme
    for document in (
        rfc,
        adr061,
        adr062,
        acceptance,
        decision_index,
        roadmap,
        brain,
        project_status,
        project_health,
        readme,
    ):
        assert "SP-020" not in document
