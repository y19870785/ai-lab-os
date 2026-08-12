"""A deterministic stand-in for the gateway/plugin side of the capability."""

from __future__ import annotations

import json
import subprocess
import sys
import time

from .protocol import FRAME_VERSION, CapabilityClient


def main() -> int:
    client = CapabilityClient.from_inherited_fd()
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
    print(
        json.dumps(
            {
                "receipt_accepted": receipt.get("accepted") is True,
                "child": json.loads(child.stdout),
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
