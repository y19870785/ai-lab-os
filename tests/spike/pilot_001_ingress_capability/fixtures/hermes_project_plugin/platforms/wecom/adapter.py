"""Inert WeCom adapter fixture for the pre-Agent capability boundary Spike."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from plugins.platforms.wecom import adapter as bundled

from .capability import (
    FRAME_VERSION,
    CapabilityClient,
    CapabilityUnavailable,
)

logger = logging.getLogger(__name__)


def authoritative_owner_dm_frame(
    payload: dict[str, Any],
    adapter: bundled.WeComAdapter,
) -> dict[str, str] | None:
    """Return a body.msgid-only frame after the existing Owner intake policy."""

    body = payload.get("body")
    if not isinstance(body, dict):
        return None
    raw_msgid = body.get("msgid")
    if not isinstance(raw_msgid, str) or not raw_msgid.strip():
        return None
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    sender_id = str(sender.get("userid") or "").strip()
    chat_id = str(body.get("chatid") or sender_id).strip()
    if not chat_id:
        return None
    is_group = str(body.get("chattype") or "").lower() == "group"
    if is_group:
        if not adapter._is_group_allowed(chat_id, sender_id):
            return None
    elif not adapter._is_dm_intake_allowed(sender_id):
        return None
    if is_group:
        return None
    return {
        "frame_version": FRAME_VERSION,
        "channel": "wecom",
        "channel_event_id": raw_msgid.strip(),
        "event_type": "owner_dm_text",
    }


class SpikeWeComAdapter(bundled.WeComAdapter):
    """Bundled behavior plus one fail-closed, pre-Agent receipt attempt."""

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self._spike_capability = CapabilityClient.from_inherited_fd()

    async def _on_message(self, payload: dict[str, Any]) -> None:
        frame = authoritative_owner_dm_frame(payload, self)
        if frame is None:
            logger.warning(
                "[IB-IMP-A] no trusted receipt: missing body.msgid or Owner DM policy mismatch"
            )
        else:
            try:
                receipt = await asyncio.to_thread(self._spike_capability.request, frame)
            except CapabilityUnavailable:
                logger.error("[IB-IMP-A] issuer unavailable; trusted evidence denied")
            else:
                digest = str(receipt.get("receipt") or "")
                logger.info(
                    "[IB-IMP-A] trusted callback receipt accepted (%s)",
                    digest[:20],
                )
        await super()._on_message(payload)

    async def disconnect(self) -> None:
        try:
            await super().disconnect()
        finally:
            self._spike_capability.close()


def _build_adapter(config: Any) -> SpikeWeComAdapter:
    return SpikeWeComAdapter(config)


def register(ctx: Any) -> None:
    """Preserve both bundled registrations, then replace only ``wecom``."""

    bundled.register(ctx)
    ctx.register_platform(
        name="wecom",
        label="WeCom (IB-IMP-A capability spike)",
        adapter_factory=_build_adapter,
        check_fn=bundled.check_wecom_requirements,
        is_connected=bundled._is_connected,
        validate_config=bundled._is_connected,
        required_env=["WECOM_BOT_ID", "WECOM_SECRET"],
        install_hint="PILOT-001 IB-IMP-A supervisor required.",
        setup_fn=bundled.interactive_setup,
        allowed_users_env="WECOM_ALLOWED_USERS",
        allow_all_env="WECOM_ALLOW_ALL_USERS",
        cron_deliver_env_var="WECOM_HOME_CHANNEL",
        standalone_sender_fn=bundled._standalone_send,
        max_message_length=4000,
        emoji="💼",
        allow_update_command=False,
    )
