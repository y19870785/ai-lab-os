"""Fail-closed process isolation for the supported PILOT-001 profile.

PILOT-001-P1B: the final Python process that will hold the issuer
capability must apply PR_SET_DUMPABLE=0 itself, prove it at runtime, and
only then enter the gateway runtime. This module is the single pilot-only
bootstrap/hardening point; it never touches Hermes source.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import runpy
import sys

PR_GET_DUMPABLE = 3
PR_SET_DUMPABLE = 4


class ProcessIsolationUnavailable(RuntimeError):
    """The required Pilot process-local hardening is unavailable or ineffective."""


def _libc() -> ctypes.CDLL:
    if os.name != "posix" or platform.system() != "Linux":
        raise ProcessIsolationUnavailable(
            "PILOT_PROCESS_ISOLATION_UNAVAILABLE: Linux is required"
        )
    return ctypes.CDLL(None, use_errno=True)


def get_dumpable() -> int:
    """Return the effective Linux dumpable state for the current process."""

    libc = _libc()
    result = libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0)
    if result < 0:
        error = ctypes.get_errno()
        raise ProcessIsolationUnavailable(
            "PILOT_PROCESS_ISOLATION_QUERY_FAILED: errno=" + str(error)
        )
    return int(result)


def assert_process_isolated(stage: str) -> int:
    """Fail closed unless the current process is still non-dumpable."""

    effective = get_dumpable()
    if effective != 0:
        raise ProcessIsolationUnavailable(
            "PILOT_PROCESS_ISOLATION_INEFFECTIVE: "
            + "stage=" + stage + " PR_GET_DUMPABLE=" + str(effective)
        )
    return effective


def apply_process_isolation() -> int:
    """Apply and verify the required process-local Pilot hardening."""

    libc = _libc()
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise ProcessIsolationUnavailable(
            "PILOT_PROCESS_ISOLATION_APPLY_FAILED: errno=" + str(error)
        )
    return assert_process_isolated("startup")


def run_hardened_module(module: str, passthrough: list[str]) -> int:
    """Apply hardening in the current (final) Python process, then enter the
    target module without any further exec boundary.

    sys.argv is rebuilt before runpy so the target module never sees the
    bootstrap arguments; the target's own arguments follow a separator.
    """

    apply_process_isolation()
    print("PILOT_PROCESS_ISOLATION_EFFECTIVE PR_GET_DUMPABLE=0", flush=True)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    sys.argv = [module + ".py"] + passthrough
    runpy.run_module(module, run_name="__main__")
    return 0


def main() -> int:
    """CLI entry: harden the final process, then run a module or self-check."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=False)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("passthrough", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.check:
        apply_process_isolation()
        print("PILOT_PROCESS_ISOLATION_EFFECTIVE PR_GET_DUMPABLE=0", flush=True)
        return 0
    if not args.module:
        parser.error("--module or --check is required")
    return run_hardened_module(args.module, list(args.passthrough))


if __name__ == "__main__":
    raise SystemExit(main())
