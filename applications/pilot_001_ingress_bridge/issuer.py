"""Local Unix-socket issuer held outside the Hermes/LLM process."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from applications.pilot_001_ingress_bridge.crypto import PilotIngressKeys
from applications.pilot_001_ingress_bridge.mcp_server import build_p1a_service
from core.errors import FailureException
from core.system import create_system, load_system_settings

MAX_FRAME_BYTES = 16 * 1024


async def _run_issuer(
    socket_path: Path | None, *, host: str = "127.0.0.1", port: int = 0,
) -> None:
    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    pilot = build_p1a_service(system)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.readline()
            if not raw or len(raw) > MAX_FRAME_BYTES:
                raise ValueError("invalid issuer frame")
            frame = json.loads(raw)
            msgid = frame.get("body_msgid")
            if not isinstance(msgid, str) or not msgid.strip():
                raise ValueError("trusted_ingress.channel_event_id_unavailable")
            envelope = pilot._keys.issue(
                raw_account_id=str(frame["account_id"]),
                raw_owner_id=str(frame["owner_id"]),
                raw_conversation_id=str(frame["conversation_id"]),
                raw_wecom_msgid=msgid,
                text=str(frame["text"]),
            )
            evidence_id = await pilot.accept_evidence(envelope)
            response = {"accepted": True, "evidence_id": evidence_id}
        except (FailureException, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            response = {"accepted": False, "code": "trusted_ingress.denied"}
        writer.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    if socket_path is not None:
        socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if socket_path.exists():
            socket_path.unlink()
        server = await asyncio.start_unix_server(handle, path=socket_path)
    else:
        if host != "127.0.0.1" or port <= 0:
            raise RuntimeError("Pilot issuer TCP must use explicit loopback port")
        server = await asyncio.start_server(handle, host=host, port=port)
    try:
        if socket_path is not None:
            os.chmod(socket_path, 0o600)
        async with server:
            await server.serve_forever()
    finally:
        await system.shutdown()
        if socket_path is not None and socket_path.exists():
            socket_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init-pilot-ingress-keys", "serve"))
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    data_dir = Path(os.environ["AI_LAB_DATA_DIR"])
    if args.command == "init-pilot-ingress-keys":
        keys = PilotIngressKeys.bootstrap(data_dir)
        print(f"Pilot ingress keys initialized: {keys.issuer_key_id}")
        return
    if args.socket is None and args.port <= 0:
        parser.error("serve requires --socket or --port")
    asyncio.run(_run_issuer(args.socket, host=args.host, port=args.port))


if __name__ == "__main__":
    main()
