"""P1B Option A spike: verify different-UID signing service blocks pidfd_getfd.

Run as root via sudo from a NON-ROOT invoking user (SUDO_USER required):

    sudo python3 run_spike.py

Model:
  holder   - protected process holding the capability FD (client end), runs
             under a configurable UID (Phase 1: attacker UID; Phase 2: dedicated
             issuer UID). This is the Option A signing service.
  verifier - orchestrator-side responder thread owning the server end; it
             answers capability invocations, proving a duplicated FD is live.

Phases:
  Phase 1 (baseline): holder shares the attacker UID -> pidfd_getfd expected
                      to DUPLICATE and INVOKE (reproduces IB-IMP-A).
  Phase 2 (isolation): holder runs under a dedicated UID -> pidfd_getfd
                      expected to FAIL (EPERM).
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAPABILITY_FD = 198
ISSUER_USER = "ailab-issuer"


def _user_uid(name: str) -> int | None:
    try:
        return pwd.getpwnam(name).pw_uid
    except KeyError:
        return None


def _ensure_issuer_user(name: str) -> int:
    uid = _user_uid(name)
    if uid is None:
        subprocess.run(["useradd", "-m", "-s", "/usr/sbin/nologin", name], check=True)
        uid = _user_uid(name)
    assert uid is not None
    return uid


def _start_verifier(server: socket.socket) -> threading.Thread:
    def _serve() -> None:
        server.settimeout(15.0)
        while True:
            try:
                raw = server.recv(4096)
            except OSError:
                return
            if not raw:
                return
            try:
                frame = json.loads(raw.split(b"\n", 1)[0])
                event_id = frame.get("channel_event_id", "")
                digest = hashlib.sha256(event_id.encode()).hexdigest()
                response = {"accepted": True, "receipt": "spike:" + digest}
            except (ValueError, AttributeError):
                response = {"accepted": False, "reason": "invalid_frame"}
            try:
                server.sendall(
                    json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
                    + b"\n"
                )
            except OSError:
                return

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    return thread


def _spawn_holder(target_uid: int, client: socket.socket) -> subprocess.Popen:
    bootstrap = os.path.join(HERE, "fd_bootstrap.py")
    holder = os.path.join(HERE, "uid_holder.py")
    proc = subprocess.Popen(
        [
            "setpriv",
            "--reuid", str(target_uid),
            "--regid", str(target_uid),
            "--clear-groups",
            sys.executable, bootstrap, "--", sys.executable, holder,
        ],
        pass_fds=(client.fileno(),),
        cwd=HERE,
    )
    time.sleep(0.5)
    return proc


def _run_attacker(target_pid: int, attacker_uid: int) -> dict[str, object]:
    attack = os.path.join(HERE, "uid_attack.py")
    completed = subprocess.run(
        [
            "setpriv",
            "--reuid", str(attacker_uid),
            "--regid", str(attacker_uid),
            "--clear-groups",
            sys.executable, attack, str(target_pid),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or f"exit {completed.returncode}"}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": "unparsable output", "raw": completed.stdout.strip()}


def main() -> int:
    if os.geteuid() != 0:
        print("must run as root: sudo python3 run_spike.py", file=sys.stderr)
        return 2
    invoking = os.environ.get("SUDO_USER", "").strip()
    if not invoking:
        print("SUDO_USER must be set: run via sudo from a non-root user", file=sys.stderr)
        return 2
    attacker_uid = _user_uid(invoking)
    if attacker_uid in (None, 0):
        print(f"attacker uid invalid for user {invoking!r}", file=sys.stderr)
        return 2

    issuer_uid = _ensure_issuer_user(ISSUER_USER)
    results: dict[str, object] = {
        "attacker_uid": attacker_uid,
        "attacker_user": invoking,
        "issuer_uid": issuer_uid,
        "issuer_user": ISSUER_USER,
    }
    yama = "/proc/sys/kernel/yama/ptrace_scope"
    if os.path.exists(yama):
        with open(yama, encoding="utf-8") as yama_file:
            results["yama_ptrace_scope"] = yama_file.read().strip()
    else:
        results["yama_ptrace_scope"] = "absent"

    def run_phase(target_uid: int) -> dict[str, object]:
        client, server = socket.socketpair()
        _start_verifier(server)
        holder = _spawn_holder(target_uid, client)
        try:
            attack = _run_attacker(holder.pid, attacker_uid)
            attack["holder_pid"] = holder.pid
            return attack
        finally:
            holder.terminate()
            holder.wait(timeout=5)
            client.close()
            server.close()

    results["phase1_same_uid"] = run_phase(attacker_uid)
    results["phase2_different_uid"] = run_phase(issuer_uid)

    phase1 = results["phase1_same_uid"]
    phase2 = results["phase2_different_uid"]
    same_uid_duplicated = isinstance(phase1, dict) and phase1.get("duplicated") is True
    same_uid_invoked = isinstance(phase1, dict) and phase1.get("invoked") is True
    different_uid_duplicated = isinstance(phase2, dict) and phase2.get("duplicated") is True
    results["verdict"] = {
        "same_uid_pidfd_getfd_duplicated": same_uid_duplicated,
        "same_uid_invoked": same_uid_invoked,
        "different_uid_pidfd_getfd_duplicated": different_uid_duplicated,
        "isolation_holds": not different_uid_duplicated,
    }
    print(json.dumps(results, sort_keys=True, indent=2))
    return 0 if (same_uid_duplicated and not different_uid_duplicated) else 1


if __name__ == "__main__":
    raise SystemExit(main())
