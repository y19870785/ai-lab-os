"""Run the real Hermes gateway under the spike-only capability supervisor."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .supervisor import supervise_forever


def main() -> int:
    if os.name != "posix":
        raise SystemExit("Run inside the real Ubuntu/WSL2 Pilot environment")
    repo = Path.cwd().resolve()
    plugin = repo / ".hermes/plugins/platforms/wecom/plugin.yaml"
    if not plugin.is_file():
        raise SystemExit("Run from the IB-IMP-A worktree root")
    env = os.environ.copy()
    env["HERMES_ENABLE_PROJECT_PLUGINS"] = "1"
    gateway = [sys.executable, "-m", "hermes_cli.main", "gateway", "run"]
    return supervise_forever(gateway, cwd=str(repo), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
