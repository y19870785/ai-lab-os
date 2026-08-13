"""Pre-Agent body.msgid-only evidence projection for a temporary Hermes project."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from plugins.platforms.wecom import adapter as bundled

OPAQUE_MARKER = "[AI_LAB_TRUSTED_INGRESS_EVIDENCE_ID:{evidence_id}]"


async def _issue(frame: dict[str, str]) -> str | None:
    endpoint = os.environ.get("AI_LAB_PILOT_001_ISSUER_SOCKET", "").strip()
    if not endpoint:
        return None
    try:
        if endpoint.startswith("tcp://"):
            host, raw_port = endpoint.removeprefix("tcp://").rsplit(":", 1)
            if host != "127.0.0.1":
                return None
            reader, writer = await asyncio.open_connection(host, int(raw_port))
        else:
            reader, writer = await asyncio.open_unix_connection(endpoint)
        writer.write(json.dumps(frame, separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        response = json.loads(await reader.readline())
        writer.close()
        await writer.wait_closed()
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    evidence_id = response.get("evidence_id") if response.get("accepted") is True else None
    return evidence_id if isinstance(evidence_id, str) else None


class PilotWeComAdapter(bundled.WeComAdapter):
    async def _on_message(self, payload: dict[str, Any]) -> None:
        body = payload.get("body")
        if not isinstance(body, dict):
            return await super()._on_message(payload)
        raw_msgid = body.get("msgid")
        sender = body.get("from") if isinstance(body.get("from"), dict) else {}
        owner_id = str(sender.get("userid") or "").strip()
        conversation_id = str(body.get("chatid") or owner_id).strip()
        is_group = str(body.get("chattype") or "").lower() == "group"
        text_block = body.get("text") if isinstance(body.get("text"), dict) else {}
        raw_text = text_block.get("content")
        allowed = (
            isinstance(raw_msgid, str)
            and bool(raw_msgid.strip())
            and not is_group
            and self._is_dm_intake_allowed(owner_id)
            and conversation_id
            and isinstance(raw_text, str)
        )
        evidence_id = None
        if allowed:
            evidence_id = await _issue(
                {
                    "account_id": self._bot_id,
                    "owner_id": owner_id,
                    "conversation_id": conversation_id,
                    "body_msgid": raw_msgid,
                    "text": raw_text,
                }
            )
        if evidence_id:
            text_block["content"] = raw_text + "\n" + OPAQUE_MARKER.format(
                evidence_id=evidence_id
            )
        await super()._on_message(payload)


def register(ctx: Any) -> None:
    bundled.register(ctx)
    ctx.register_platform(
        name="wecom",
        label="WeCom (PILOT-001 internal trusted ingress)",
        adapter_factory=PilotWeComAdapter,
        check_fn=bundled.check_wecom_requirements,
        is_connected=bundled._is_connected,
        validate_config=bundled._is_connected,
        required_env=["WECOM_BOT_ID", "WECOM_SECRET"],
        install_hint="PILOT-001 temporary launcher required.",
        setup_fn=bundled.interactive_setup,
        allowed_users_env="WECOM_ALLOWED_USERS",
        allow_all_env="WECOM_ALLOW_ALL_USERS",
        cron_deliver_env_var="WECOM_HOME_CHANNEL",
        standalone_sender_fn=bundled._standalone_send,
        max_message_length=4000,
        emoji="💼",
        allow_update_command=False,
    )
