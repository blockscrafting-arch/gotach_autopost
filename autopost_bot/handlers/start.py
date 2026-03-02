# -*- coding: utf-8 -*-
"""Start command."""

from telegram import Update
from telegram.ext import ContextTypes

from autopost_bot.config import get_settings


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if settings.is_admin(update.effective_user.id if update.effective_user else 0):
        await update.message.reply_text(
            "Привет. Отправь черновик или заметку — я превращу в пост и пришлю на утверждение. "
            "Кнопки: Переделать, Отредактировать, Опубликовать.\n/cancel — отменить текущий пост."
        )
    else:
        await update.message.reply_text("Доступ только для администратора.")
