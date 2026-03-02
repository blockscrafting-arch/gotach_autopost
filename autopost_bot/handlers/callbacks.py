# -*- coding: utf-8 -*-
"""Callback handlers for approval buttons: Переделать, Отредактировать, Опубликовать."""

from __future__ import annotations

import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from autopost_bot.config import get_reference_photo_bytes, get_settings
from autopost_bot.formatter.tg_html import validate_for_telegram
from autopost_bot.prompts.system_prompt import (
    SYSTEM_PROMPT,
    build_edit_message,
    build_user_message,
)
from autopost_bot.publisher.channel import publish_to_channel

# Keys for context.user_data
KEY_CURRENT_POST = "current_post"
KEY_CURRENT_DRAFT = "current_draft"
KEY_CURRENT_IMAGE = "current_image"  # bytes | None
KEY_STATE = "state"

# Caption limit for Telegram (send_photo)
TELEGRAM_CAPTION_MAX_LENGTH = 1024

STATE_IDLE = "idle"
STATE_AWAITING_APPROVAL = "awaiting_approval"
STATE_AWAITING_EDIT = "awaiting_edit"

# For ConversationHandler.END


def _approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Переделать", callback_data="post_redo"),
            InlineKeyboardButton("Отредактировать", callback_data="post_edit"),
            InlineKeyboardButton("Опубликовать", callback_data="post_publish"),
        ]
    ])


async def _generate_post(draft: str) -> str:
    """Run AI generation in thread (blocking)."""
    from autopost_bot.ai.provider import generate_post as ai_generate
    from autopost_bot.config import get_settings
    s = get_settings()
    return await asyncio.to_thread(
        ai_generate,
        system_prompt=SYSTEM_PROMPT,
        user_message=build_user_message(draft),
        gemini_keys=s.get_gemini_keys(),
        openrouter_key=s.openrouter_api_key or None,
        model=s.gemini_model,
    )


async def _generate_post_image(post_summary: str) -> bytes | None:
    """Generate one image for the post (Gemini 3.1 Flash Image). Returns bytes or None."""
    from autopost_bot.ai import image_client
    from autopost_bot.config import get_settings
    settings = get_settings()
    keys = settings.get_gemini_keys()
    if not keys:
        return None
    refs = get_reference_photo_bytes(settings)
    summary = (post_summary or "")[:1000]
    for api_key in keys:
        result = await asyncio.to_thread(
            image_client.generate_post_image,
            api_key=api_key,
            model=settings.gemini_image_model,
            post_text_or_summary=summary,
            reference_photo_bytes=refs,
        )
        if result:
            return result
    return None


async def _send_preview_with_buttons(msg, cleaned: str, image_bytes: bytes | None) -> None:
    """Send post preview: photo+caption or text only; caption limited to 1024."""
    keyboard = _approval_keyboard()
    if image_bytes:
        caption = (
            cleaned
            if len(cleaned) <= TELEGRAM_CAPTION_MAX_LENGTH
            else cleaned[: TELEGRAM_CAPTION_MAX_LENGTH - 3].rstrip() + "..."
        )
        try:
            await msg.reply_photo(
                photo=image_bytes,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            await msg.reply_photo(photo=image_bytes, caption=caption, reply_markup=keyboard)
        if len(cleaned) > TELEGRAM_CAPTION_MAX_LENGTH:
            await msg.reply_text(cleaned, parse_mode="HTML")
    else:
        try:
            await msg.reply_text(cleaned, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await msg.reply_text(cleaned, reply_markup=keyboard)


async def callback_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | int:
    """
    Handle inline button press. Returns next state for ConversationHandler.
    """
    from telegram.ext import ConversationHandler

    query = update.callback_query
    await query.answer()
    if not query.data or not query.from_user:
        return ConversationHandler.END
    if not query.message:
        return ConversationHandler.END

    user_data = context.user_data
    current_post = user_data.get(KEY_CURRENT_POST)
    current_draft = user_data.get(KEY_CURRENT_DRAFT)
    settings = get_settings()

    if not settings.is_admin(query.from_user.id):
        await query.message.reply_text("Доступ только для администратора.")
        return ConversationHandler.END

    if query.data == "post_redo":
        if not current_draft:
            await query.message.reply_text("Черновик потерян. Отправь текст заново.")
            return ConversationHandler.END
        await query.edit_message_text("Переделываю...")
        try:
            new_post = await _generate_post(current_draft)
        except Exception as e:
            from loguru import logger
            logger.warning("Redo generation failed: {}", e)
            await query.message.reply_text("Сервис временно недоступен. Нажми «Переделать» ещё раз.")
            return STATE_AWAITING_APPROVAL
        _, cleaned = validate_for_telegram(new_post)
        user_data[KEY_CURRENT_POST] = cleaned
        await query.edit_message_text("Генерирую картинку...")
        image_bytes = await _generate_post_image(cleaned)
        user_data[KEY_CURRENT_IMAGE] = image_bytes
        await _send_preview_with_buttons(query.message, cleaned, image_bytes)
        return STATE_AWAITING_APPROVAL

    if query.data == "post_edit":
        await query.message.reply_text("Напиши правки текстом. Я применю их к посту и пришлю новый вариант.")
        return STATE_AWAITING_EDIT

    if query.data == "post_publish":
        if not current_post:
            await query.message.reply_text("Пост потерян. Отправь черновик заново.")
            return ConversationHandler.END
        if not (settings.channel_id and settings.channel_id.strip()):
            await query.message.reply_text("Канал не настроен. Укажи CHANNEL_ID в .env")
            return STATE_AWAITING_APPROVAL
        image_bytes = user_data.get(KEY_CURRENT_IMAGE)
        success = await publish_to_channel(
            context.bot,
            settings.channel_id,
            current_post,
            image_bytes=image_bytes,
        )
        if success:
            await query.message.reply_text("Опубликовано в канал.")
        else:
            await query.message.reply_text("Не удалось опубликовать. Проверь CHANNEL_ID и права бота.")
        user_data.pop(KEY_CURRENT_POST, None)
        user_data.pop(KEY_CURRENT_DRAFT, None)
        user_data.pop(KEY_CURRENT_IMAGE, None)
        return ConversationHandler.END

    return STATE_AWAITING_APPROVAL


async def apply_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """User sent edit text. Run AI to apply edits, then show preview again."""
    from telegram.ext import ConversationHandler
    settings = get_settings()
    if not update.effective_user or not settings.is_admin(update.effective_user.id):
        if update.message:
            await update.message.reply_text("Доступ только для администратора.")
        return ConversationHandler.END
    user_data = context.user_data
    current_post = user_data.get(KEY_CURRENT_POST)
    edits = update.message and update.message.text
    if not current_post or not edits:
        return ConversationHandler.END

    await update.message.reply_text("Применяю правки...")
    from autopost_bot.ai.provider import generate_post as ai_generate
    try:
        new_post = await asyncio.to_thread(
            ai_generate,
            system_prompt=SYSTEM_PROMPT,
            user_message=build_edit_message(current_post, edits.strip()),
            gemini_keys=settings.get_gemini_keys(),
            openrouter_key=settings.openrouter_api_key or None,
            model=settings.gemini_model,
        )
    except Exception as e:
        from loguru import logger
        logger.warning("Apply edit failed: {}", e)
        await update.message.reply_text("Сервис временно недоступен. Попробуй ещё раз написать правки.")
        return STATE_AWAITING_EDIT

    ok, cleaned = validate_for_telegram(new_post)
    user_data[KEY_CURRENT_POST] = cleaned
    await update.message.reply_text("Генерирую картинку...")
    image_bytes = await _generate_post_image(cleaned)
    user_data[KEY_CURRENT_IMAGE] = image_bytes
    await _send_preview_with_buttons(update.message, cleaned, image_bytes)
    return STATE_AWAITING_APPROVAL
