from __future__ import annotations

import json
import re
import subprocess
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

    assert f"v{state['current_version']} Alpha Candidate" in readme
    assert f"Product Version: {state['version']}" in brain
    assert f"Last Completed SP: {state['latest_completed_sp']}" in brain
    assert f"Current SP: {state['current_sp']}" in brain
    assert f"Next Candidate SP: {state['next_candidate_sp']}" in brain
    assert state["main_commit"] in brain


def test_main_commit_and_sp_progression_are_well_formed() -> None:
    state = _load_state()
    assert re.fullmatch(r"[0-9a-f]{40}", state["main_commit"])

    records = state["sp_records"]
    completed_numbers = [
        _sp_number(sp_id)
        for sp_id, record in records.items()
        if "ARCHIVED" in record["status"]
    ]
    assert _sp_number(state["latest_completed_sp"]) == max(completed_numbers)

    assert state["current_sp"] is None
    assert state["current_governance_task"] == "SP-015A"
    assert records[state["current_governance_task"]]["status"] == (
        "IN_PROGRESS / DRAFT_PR_OPEN"
    )
    assert _sp_number(state["next_candidate_sp"]) > _sp_number(
        state["latest_completed_sp"]
    )


def test_sp015_merge_and_post_merge_acceptance_are_archived() -> None:
    state = _load_state()
    sp015 = state["sp_records"]["SP-015"]

    assert state["main_commit"] == "01166352224ddce5e859d4133f502aee1f97da07"
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
        "run_id": 29738408215,
        "head_sha": "01166352224ddce5e859d4133f502aee1f97da07",
        "environment": "ubuntu-latest / Python 3.12",
        "command": 'python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no',
        "ruff": "SUCCESS",
        "pytest": "SUCCESS",
        "passed": 1162,
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


def test_sp015a_and_sp016_candidate_state_is_consistent() -> None:
    state = _load_state()
    records = state["sp_records"]
    candidate_name = "Follow-up & Waiting-For Workflow"
    candidate_status = "CANDIDATE / NOT_APPROVED / NOT_STARTED"
    sp015a_status = "IN_PROGRESS / DRAFT_PR_OPEN"

    assert records["SP-015A"]["status"] == sp015a_status
    assert records["SP-015A"]["implementation_started"] is True
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
    }
    text = {
        name: path.read_text(encoding="utf-8-sig") for name, path in documents.items()
    }

    assert f"| SP-015A | {sp015a_status} |" in text["status"]
    assert f"| SP-016 | {candidate_name} / {candidate_status} |" in text["status"]
    assert f"| SP-016 | {candidate_name} | {candidate_status} |" in text["roadmap"]
    assert f"> Next Candidate Direction: {candidate_name}" in text["brain"]
    assert f"> SP-015A Status: {sp015a_status}" in text["brain"]
    assert "Last Completed SP: SP-015" in text["brain"]
    assert "Current SP: None" in text["brain"]
    assert "SP-015A / IN_PROGRESS / DRAFT_PR_OPEN" in text["health"]
    assert "Alpha Candidate / VERIFIED / UNPUBLISHED" in text["health"]
    assert "**Verification:** Verified / Unpublished" in text["version_matrix"]
    assert "SP-015 archived after post-merge acceptance" in text["release_checklist"]
    assert f"SP-016 {candidate_name}" in text["release_notes"]
    stale_candidate = "SP-016 " + "Notification" + " Delivery"
    assert all(stale_candidate not in content for content in text.values())


def test_release_is_still_an_unpublished_alpha_candidate() -> None:
    state = _load_state()
    release = state["release_status"]
    release_notes = (ROOT / "docs/releases/v0.34.0-alpha.md").read_text(
        encoding="utf-8-sig"
    )

    assert release["release_stage"] == "alpha_candidate"
    assert release["verification"] == "VERIFIED / UNPUBLISHED"
    assert release["tag_created"] is False
    assert release["tag_name"] is None
    assert release["github_release_created"] is False
    assert release["github_release_url"] is None
    assert "Alpha / local-first / single-user-oriented" in release_notes
    assert "Tag and GitHub Release not created" in release_notes

    tag = subprocess.run(
        ["git", "tag", "--list", "v0.34.0"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert tag.stdout.strip() == ""


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
