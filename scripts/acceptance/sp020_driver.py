"""ACC-020 evidence driver scaffold; formal scenarios require a frozen Head."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_manifest(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def run_command(command: list[str], *, env: dict[str, str]) -> dict[str, object]:
    started = datetime.now(UTC)
    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    return {
        "command": command,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-head", required=True)
    parser.add_argument("--source-data-root", type=Path, required=True)
    parser.add_argument("--restore-data-root", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    source = args.source_data_root.resolve()
    restore = args.restore_data_root.resolve()
    if not args.source_data_root.is_absolute() or not args.restore_data_root.is_absolute():
        raise SystemExit("INVALID_ACCEPTANCE_HARNESS: data roots must be absolute")
    if source == restore:
        raise SystemExit("INVALID_ACCEPTANCE_HARNESS: roots must be distinct")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    driver = Path(__file__).resolve()
    record = {
        "status": "PREPARED_NOT_EXECUTED" if args.prepare_only else "NOT_EXECUTED",
        "frozen_head": args.frozen_head,
        "driver_sha256": sha256(driver),
        "python_version": sys.version,
        "utc_time": datetime.now(UTC).isoformat(),
        "windows_local_time": datetime.now().astimezone().isoformat(),
        "source_data_root": str(source),
        "restore_data_root": str(restore),
        "api_pid": None,
        "api_port": args.api_port,
        "config_summary": {
            "provider_mode": os.getenv("AI_LAB_PROVIDER_MODE"),
            "api_token": (
                "configured" if os.getenv("AI_LAB_API_TOKEN") else "not configured"
            ),
        },
        "commands": [],
        "provider_spy_call_count": 0,
        "sqlite_files": file_manifest(source) if source.exists() else [],
        "mutations": [],
        "canonical_ids": [],
        "workspace": {},
        "revisions": [],
        "idempotency_keys": [],
        "claims_and_sagas": [],
        "confirmations": [],
        "event_bus": [],
        "connection_counts": [],
    }
    output = args.evidence_dir / "manifest.json"
    output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
