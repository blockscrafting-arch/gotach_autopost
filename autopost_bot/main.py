# -*- coding: utf-8 -*-
"""Entry point: long polling and graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from loguru import logger

from autopost_bot.config import get_settings
from autopost_bot.handlers.conversation import build_conversation_handler
from autopost_bot.handlers.start import start


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level=logging.INFO,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )


def main() -> None:
    setup_logging()
    settings = get_settings()

    if not settings.bot_token:
        logger.error("BOT_TOKEN not set. Create .env from .env.example")
        sys.exit(1)
    if not (settings.channel_id and settings.channel_id.strip()):
        logger.error("CHANNEL_ID not set. Set it in .env (e.g. @channel or -100...)")
        sys.exit(1)
    keys = settings.get_gemini_keys()
    openrouter = (settings.openrouter_api_key or "").strip()
    if not keys and not openrouter:
        logger.error("No AI provider: set GEMINI_API_KEY_1/2 or OPENROUTER_API_KEY in .env")
        sys.exit(1)

    from telegram.ext import Application, PicklePersistence

    Path("data").mkdir(exist_ok=True)
    persistence = PicklePersistence(filepath="data/bot_persistence.pickle")

    application = (
        Application.builder()
        .token(settings.bot_token)
        .persistence(persistence)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(build_conversation_handler())

    logger.info("Starting long polling...")
    application.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)


async def _post_init(application) -> None:
    logger.info("Bot started.")


async def _post_shutdown(application) -> None:
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
