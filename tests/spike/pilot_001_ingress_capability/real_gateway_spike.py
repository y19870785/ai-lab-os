"""Run the real Hermes gateway under the spike-only capability supervisor."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from .supervisor import supervise_forever


def main() -> int:
    if os.name != "posix":
        raise SystemExit("Run inside the real Ubuntu/WSL2 Pilot environment")
    repo = Path.cwd().resolve()
    fixture = (
        repo
        / "tests/spike/pilot_001_ingress_capability/fixtures/"
        "hermes_project_plugin"
    )
    if not (fixture / "platforms/wecom/plugin.yaml").is_file():
        raise SystemExit("Run from the IB-IMP-A worktree root")
    with tempfile.TemporaryDirectory(prefix="pilot001-ib-imp-a-") as temp_dir:
        project_root = Path(temp_dir)
        shutil.copytree(fixture, project_root / ".hermes/plugins")
        env = os.environ.copy()
        env["HERMES_ENABLE_PROJECT_PLUGINS"] = "1"
        gateway = [sys.executable, "-m", "hermes_cli.main", "gateway", "run"]
        return supervise_forever(gateway, cwd=str(project_root), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
