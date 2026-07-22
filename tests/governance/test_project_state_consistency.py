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
    assert _sp_number(state["next_candidate_sp"]) > _sp_number(
        state["latest_completed_sp"]
    )


def test_sp015_merge_and_current_main_quality_gate_are_archived() -> None:
    state = _load_state()
    sp015 = state["sp_records"]["SP-015"]

    assert state["latest_merged_sp"] == "SP-015"
    assert state["latest_completed_sp"] == "SP-015"
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


def test_sp015a_sp015r_and_sp016_candidate_state_is_consistent() -> None:
    state = _load_state()
    records = state["sp_records"]
    candidate_name = "Follow-up & Waiting-For Workflow"
    candidate_status = "CANDIDATE / NOT_APPROVED / NOT_STARTED"
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
    assert state["next_candidate_sp"] == "SP-016"
    assert state["next_candidate_name"] == candidate_name
    assert records["SP-016"]["name"] == candidate_name
    assert records["SP-016"]["status"] == candidate_status
    assert records["SP-016"]["approved"] is False
    assert records["SP-016"]["implementation_started"] is False

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
    assert f"| SP-016 | {candidate_name} / {candidate_status} |" in text["status"]
    assert f"| SP-016 | {candidate_name} | {candidate_status} |" in text["roadmap"]
    assert f"> Next Candidate Direction: {candidate_name}" in text["brain"]
    assert f"> SP-015A Status: {sp015a_status}" in text["brain"]
    assert f"> SP-015R Status: {sp015r_status}" in text["brain"]
    assert "Last Completed SP: SP-015" in text["brain"]
    assert "Current SP: None" in text["brain"]
    assert "Current governance task | None" in text["health"]
    assert "Alpha / RELEASE_AUTHORIZED" in text["health"]
    assert "**Authorization:** Release Authorized" in text["version_matrix"]
    assert (
        "SP-015, SP-015A and SP-015R archived; SP-016 remains candidate only"
        in text["release_checklist"]
    )
    assert f"SP-016 {candidate_name}" in text["release_notes"]
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
