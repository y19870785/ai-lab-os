"""Explicit local operator entrypoint for the P1A issuer and MCP processes."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from applications.pilot_001_ingress_bridge.crypto import PilotIngressKeys
from applications.pilot_001_ingress_bridge.issuer import _run_issuer
from applications.pilot_001_ingress_bridge.mcp_server import _serve_stdio


def _load_pilot_environment(ai_lab_env: Path, hermes_env: Path) -> Path:
    if not ai_lab_env.is_file() or not hermes_env.is_file():
        raise RuntimeError("P1A requires explicit AI-Lab and Hermes env files")
    load_dotenv(ai_lab_env, override=True)
    load_dotenv(hermes_env, override=True)
    owner = os.environ.get("AI_LAB_PILOT_001_OWNER_CHANNEL_IDENTITY", "").strip()
    account = os.environ.get("WECOM_BOT_ID", "").strip()
    if not owner or not account:
        raise RuntimeError("P1A Owner and WeCom account bindings are incomplete")
    os.environ.update(
        {
            "AI_LAB_PROVIDER_MODE": "mock",
            "OPENAI_API_KEY": "DISABLED",
            "AI_LAB_LLM_API_KEY": "DISABLED",
            "DEEPSEEK_API_KEY": "DISABLED",
            "AI_LAB_PILOT_001_MODE": "internal_trusted_ingress_confirmation",
            "AI_LAB_PILOT_001_EXPECTED_SHELL": "hermes",
            "AI_LAB_PILOT_001_EXPECTED_CHANNEL": "wecom",
            "AI_LAB_PILOT_001_CHANNEL_ACCOUNT_ID": account,
            "AI_LAB_PILOT_001_CONVERSATION_ID": owner,
        }
    )
    data_dir = Path(os.environ["AI_LAB_DATA_DIR"])
    os.environ.setdefault("AI_LAB_SQLITE_DIR", str(data_dir / "sqlite"))
    return data_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init-keys", "serve-issuer", "serve-mcp"))
    parser.add_argument("--ai-lab-env", type=Path, required=True)
    parser.add_argument("--hermes-env", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    data_dir = _load_pilot_environment(args.ai_lab_env, args.hermes_env)
    if args.command == "init-keys":
        keys = PilotIngressKeys.bootstrap(data_dir)
        print(f"Pilot ingress keys initialized: {keys.issuer_key_id}")
    elif args.command == "serve-issuer":
        asyncio.run(_run_issuer(None, port=args.port))
    else:
        asyncio.run(_serve_stdio())


if __name__ == "__main__":
    main()
