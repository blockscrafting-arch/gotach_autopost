# -*- coding: utf-8 -*-
"""Handle incoming draft (text or voice)."""

from __future__ import annotations

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from autopost_bot.config import get_settings
from autopost_bot.formatter.tg_html import validate_for_telegram
from autopost_bot.prompts.system_prompt import SYSTEM_PROMPT, build_user_message

from .callbacks import (
    KEY_CURRENT_DRAFT,
    KEY_CURRENT_IMAGE,
    KEY_CURRENT_POST,
    STATE_AWAITING_APPROVAL,
    _generate_post,
    _generate_post_image,
    _send_preview_with_buttons,
)


async def handle_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    User sent a text draft. Generate post and send preview with buttons.
    Returns next state for ConversationHandler.
    """
    if not update.message or not update.message.text:
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    settings = get_settings()
    if not settings.is_admin(update.message.from_user.id if update.message.from_user else 0):
        await update.message.reply_text("Доступ только для администратора.")
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    draft = update.message.text.strip()
    if not draft:
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    await update.message.reply_text("Генерирую пост...")
    try:
        post = await _generate_post(draft)
    except Exception as e:
        from loguru import logger
        logger.warning("Draft generation failed: {}", e)
        await update.message.reply_text("Ошибка генерации. Сервис временно недоступен.")
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    _, cleaned = validate_for_telegram(post)
    context.user_data[KEY_CURRENT_DRAFT] = draft
    context.user_data[KEY_CURRENT_POST] = cleaned

    await update.message.reply_text("Генерирую картинку...")
    image_bytes = await _generate_post_image(cleaned)
    context.user_data[KEY_CURRENT_IMAGE] = image_bytes

    await _send_preview_with_buttons(update.message, cleaned, image_bytes)
    return STATE_AWAITING_APPROVAL


async def handle_voice_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    User sent voice. For MVP we treat it as unsupported and ask for text.
    Later: download voice, transcribe (Whisper/Gemini), then same flow as text.
    """
    from telegram.ext import ConversationHandler
    if not update.message:
        return ConversationHandler.END
    await update.message.reply_text("Пока принимаю только текст. Напиши черновик сообщением.")
    return ConversationHandler.END
