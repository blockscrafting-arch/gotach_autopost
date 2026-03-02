# -*- coding: utf-8 -*-
"""Publish post to Telegram channel."""

from __future__ import annotations

from loguru import logger


TELEGRAM_MESSAGE_MAX_LENGTH = 4096
TELEGRAM_CAPTION_MAX_LENGTH = 1024

async def publish_to_channel(
    bot,
    channel_id: str,
    post_html: str,
    *,
    image_bytes: bytes | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send post to channel. Returns True on success.
    bot: telegram.Bot (or application.bot)
    channel_id: @channel_username or -100xxxxxxxxxx
    image_bytes: optional image to send with post as photo (caption = post text, max 1024).
    """
    if not channel_id or not channel_id.strip():
        logger.error("Publish skipped: CHANNEL_ID is empty")
        return False
    if len(post_html) > TELEGRAM_MESSAGE_MAX_LENGTH:
        logger.warning(
            "Post truncated from %s to %s chars",
            len(post_html),
            TELEGRAM_MESSAGE_MAX_LENGTH,
        )
        post_html = post_html[: TELEGRAM_MESSAGE_MAX_LENGTH - 3].rstrip() + "..."
    try:
        if image_bytes:
            caption = (
                post_html
                if len(post_html) <= TELEGRAM_CAPTION_MAX_LENGTH
                else post_html[: TELEGRAM_CAPTION_MAX_LENGTH - 3].rstrip() + "..."
            )
            await bot.send_photo(
                chat_id=channel_id,
                photo=image_bytes,
                caption=caption,
                parse_mode=parse_mode,
            )
            if len(post_html) > TELEGRAM_CAPTION_MAX_LENGTH:
                await bot.send_message(
                    chat_id=channel_id,
                    text=post_html,
                    parse_mode=parse_mode,
                )
        else:
            await bot.send_message(
                chat_id=channel_id,
                text=post_html,
                parse_mode=parse_mode,
            )
        logger.info("Published to channel %s", channel_id)
        return True
    except Exception as e:
        logger.error("Publish failed: %s", e)
        return False
