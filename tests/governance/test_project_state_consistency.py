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

    current_record = records[state["current_sp"]]
    assert current_record["status"] == "IN_PROGRESS"
    assert "ARCHIVED" not in current_record["status"]
    assert _sp_number(state["current_sp"]) > _sp_number(state["latest_completed_sp"])
    assert _sp_number(state["next_candidate_sp"]) > _sp_number(state["current_sp"])


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
    sp015a_status = "NOT_STARTED / BLOCKED_UNTIL_SP-015_MERGED"

    assert records["SP-015A"]["status"] == sp015a_status
    assert records["SP-015A"]["implementation_started"] is False
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
