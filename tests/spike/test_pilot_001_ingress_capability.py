"""PILOT-001 IB-IMP-A capability boundary attack suite."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests.spike.pilot_001_ingress_capability.issuer_stub import _receipt
from tests.spike.pilot_001_ingress_capability.protocol import (
    FRAME_VERSION,
    CapabilityClient,
    CapabilityUnavailable,
)
from tests.spike.pilot_001_ingress_capability.supervisor import spawn_with_capability

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PLUGIN = (
    ROOT
    / "tests/spike/pilot_001_ingress_capability/fixtures/"
    "hermes_project_plugin/platforms/wecom"
)
PLUGIN = FIXTURE_PLUGIN / "adapter.py"
LIVE_PLUGIN = ROOT / ".hermes/plugins/platforms/wecom"
HERMES_CORE = ROOT / "hermes_core"


def _valid_frame() -> dict[str, str]:
    return {
        "frame_version": FRAME_VERSION,
        "channel": "wecom",
        "channel_event_id": "spike-redacted-event",
        "event_type": "owner_dm_text",
    }


def test_spike_a_project_plugin_loads_only_from_projected_fixture(
    tmp_path: Path,
) -> None:
    projected_root = tmp_path / ".hermes/plugins"
    projected_plugin = projected_root / "platforms/wecom"
    shutil.copytree(FIXTURE_PLUGIN, projected_plugin)

    manifest = (projected_plugin / "plugin.yaml").read_text(encoding="utf-8")
    source = (projected_plugin / "adapter.py").read_text(encoding="utf-8")
    assert projected_plugin.is_dir()
    assert "PILOT_SPIKE_ONLY" in manifest
    assert "NOT_PRODUCT_RUNTIME" in manifest
    assert "def register(ctx" in source
    assert "bundled.register(ctx)" in source

    if os.environ.get("PILOT001_RUN_HERMES_LOADER_PROBE") == "1":
        from hermes_cli.plugins import PluginManager

        manager = PluginManager()
        discovered = manager._scan_directory(projected_root, source="project")
        matches = [item for item in discovered if item.key == "platforms/wecom"]
        assert len(matches) == 1
        manager._load_plugin(matches[0])
        loaded = manager._plugins["platforms/wecom"]
        assert loaded.enabled is True
        assert loaded.error is None


def test_spike_b_authoritative_id_is_body_msgid_only() -> None:
    source = PLUGIN.read_text(encoding="utf-8")
    assert 'raw_msgid = body.get("msgid")' in source
    assert '"channel_event_id": raw_msgid.strip()' in source
    assert "req_id" not in source
    assert "uuid" not in source


def test_spike_c_strict_callback_frame_gets_test_receipt() -> None:
    receipt = _receipt(_valid_frame())
    assert receipt["accepted"] is True
    assert str(receipt["receipt"]).startswith("spike:")


def test_spike_d_arbitrary_or_fallback_frame_is_denied() -> None:
    for frame in (
        {**_valid_frame(), "arbitrary": "field"},
        {**_valid_frame(), "channel_event_id": ""},
        {**_valid_frame(), "channel": "mcp"},
        {**_valid_frame(), "event_type": "tool_assertion"},
    ):
        assert _receipt(frame) == {"accepted": False, "reason": "invalid_frame"}


def test_spike_e_f_tool_child_is_closed_but_real_same_user_attack_succeeds() -> None:
    if os.name != "posix" or os.environ.get("PILOT001_RUN_REAL_CAPABILITY_ATTACK") != "1":
        # The authoritative execution is the explicit WSL2 spike run.  Windows
        # still verifies that no product path is imported or modified.
        assert not HERMES_CORE.exists()
        return

    plugin_endpoint, issuer_endpoint = socket.socketpair()
    issuer = spawn_with_capability(
        [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.issuer_stub"],
        issuer_endpoint,
        cwd=str(ROOT),
        env=os.environ.copy(),
    )
    gateway = spawn_with_capability(
        [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.gateway_probe"],
        plugin_endpoint,
        cwd=str(ROOT),
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    plugin_endpoint.close()
    issuer_endpoint.close()
    try:
        assert gateway.stdout is not None
        holder_result = json.loads(gateway.stdout.readline())
        assert holder_result["receipt_accepted"] is True
        assert holder_result["child"] == {"fd_visible": False}

        attacker = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.spike.pilot_001_ingress_capability.attack_probe",
                str(gateway.pid),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        attack_result = json.loads(attacker.stdout)
        assert attack_result["fd_in_environment"] is False
        assert attack_result["fd_in_argv"] is False
        assert attack_result["proc_duplicated"] is False
        assert attack_result["pidfd_getfd"]["duplicated"] is True
        assert attack_result["pidfd_getfd"]["invoked"] is True
    finally:
        gateway.terminate()
        issuer.terminate()
        gateway.wait(timeout=5.0)
        issuer.wait(timeout=5.0)


def test_spike_g_h_has_no_named_endpoint_or_bearer() -> None:
    supervisor = (
        ROOT / "tests/spike/pilot_001_ingress_capability/supervisor.py"
    ).read_text(encoding="utf-8")
    plugin = PLUGIN.read_text(encoding="utf-8")
    assert "socket.socketpair()" in supervisor
    assert "AF_UNIX" not in supervisor
    assert "bind(" not in supervisor
    assert "listen(" not in supervisor
    assert "TOKEN" not in plugin.upper()
    assert "BEARER" not in plugin.upper()


def test_spike_i_issuer_unavailable_fails_closed() -> None:
    client_endpoint, issuer_endpoint = socket.socketpair()
    client = CapabilityClient.from_socket(client_endpoint)
    issuer_endpoint.close()
    try:
        with pytest.raises(CapabilityUnavailable):
            client.request(_valid_frame())
    finally:
        client.close()


def test_spike_j_restart_invalidates_old_endpoint() -> None:
    old_client_endpoint, old_issuer_endpoint = socket.socketpair()
    old_fd = old_client_endpoint.fileno()
    old_client = CapabilityClient.from_socket(old_client_endpoint)
    old_issuer_endpoint.close()
    with pytest.raises(CapabilityUnavailable):
        old_client.request(_valid_frame())
    old_client.close()

    new_client_endpoint, new_issuer_endpoint = socket.socketpair()
    try:
        assert old_fd >= 0
        assert new_client_endpoint.fileno() >= 0
        assert new_issuer_endpoint.fileno() >= 0
    finally:
        new_client_endpoint.close()
        new_issuer_endpoint.close()


def test_spike_k_l_no_business_or_hermes_core_implementation() -> None:
    changed_product_roots = (
        ROOT / "applications",
        ROOT / "core",
        ROOT / "database",
    )
    assert all(path.is_dir() for path in changed_product_roots)
    assert not HERMES_CORE.exists()
    plugin = PLUGIN.read_text(encoding="utf-8")
    for forbidden in (
        "TrustedIngressEvidence",
        "UserTask",
        "Confirmation",
        "preview_confirmation_challenge",
        "Ed25519",
    ):
        assert forbidden not in plugin


def test_spike_m_failed_plugin_is_not_live_discoverable() -> None:
    assert not LIVE_PLUGIN.exists()
    assert FIXTURE_PLUGIN.is_dir()
    manifest = (FIXTURE_PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
    assert "PILOT_SPIKE_ONLY" in manifest
    assert "NOT_PRODUCT_RUNTIME" in manifest
