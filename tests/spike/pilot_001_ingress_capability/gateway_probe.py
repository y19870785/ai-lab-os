"""A deterministic stand-in for the gateway/plugin side of the capability."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from applications.pilot_001_ingress_bridge.process_isolation import (
    apply_process_isolation,
    assert_process_isolated,
)

from .protocol import FRAME_VERSION, CapabilityClient


def main() -> int:
    hardening: dict[str, int] = {}
    if os.environ.get("PILOT001_REQUIRE_PROCESS_ISOLATION") == "1":
        hardening["startup"] = apply_process_isolation()
    client = CapabilityClient.from_inherited_fd()
    if hardening:
        hardening["capability_acquired"] = assert_process_isolated(
            "capability_acquired"
        )
    receipt = client.request(
        {
            "frame_version": FRAME_VERSION,
            "channel": "wecom",
            "channel_event_id": "spike-redacted-event",
            "event_type": "owner_dm_text",
        }
    )
    child = subprocess.run(
        [sys.executable, "-m", "tests.spike.pilot_001_ingress_capability.attack_probe"],
        check=True,
        capture_output=True,
        text=True,
        close_fds=False,
    )
    if hardening:
        hardening["post_child"] = assert_process_isolated("post_child")
    print(
        json.dumps(
            {
                "receipt_accepted": receipt.get("accepted") is True,
                "child": json.loads(child.stdout),
                "hardening": hardening,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    time.sleep(30.0)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
