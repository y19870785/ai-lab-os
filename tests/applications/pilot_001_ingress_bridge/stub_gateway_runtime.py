"""Pilot-only stub gateway runtime for P1B-R1 actual-path testing.

This module intentionally mirrors the role of Hermes `gateway.run` without
touching Hermes source: it is the module the launcher enters through the
process_isolation bootstrap, sleeps briefly (simulating runtime
initialization), and then exits 0.  It lets the launcher's actual
run_pilot_gateway() path be exercised end-to-end on a real Linux/WSL2
process while staying fully local, deterministic and side-effect free.

It must never be imported by product code; it exists only for the explicit
P1B-R1 acceptance test.
"""

from __future__ import annotations

import os
import time


def main() -> int:
    # Keep the process alive long enough for the launcher to observe the
    # evidence file and read the kernel dumpable state from /proc/<pid>/status.
    time.sleep(2.0)
    # Optional: verify the evidence file is present and names this PID.
    evidence_env = "PILOT001_RUNTIME_EVIDENCE_FILE"
    if os.environ.get(evidence_env):
        from pathlib import Path

        path = Path(os.environ[evidence_env])
        if path.is_file():
            import json

            evidence = json.loads(path.read_text(encoding="utf-8"))
            assert evidence.get("pid") == os.getpid(), evidence
            assert evidence.get("dumpable") == 0, evidence
    return 0


if __name__ == "__main__":
    # Deliberately return normally (not SystemExit) so the bootstrap's
    # post-runtime evidence write can prove the same process survived the
    # entire gateway runtime and can still observe its own identity.
    main()
