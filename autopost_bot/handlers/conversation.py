# -*- coding: utf-8 -*-
"""ConversationHandler: draft -> preview -> redo/edit/publish."""

from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from autopost_bot.handlers.callbacks import (
    STATE_AWAITING_APPROVAL,
    STATE_AWAITING_EDIT,
    apply_edit,
    callback_approval,
)
from autopost_bot.handlers.draft import handle_draft, handle_voice_draft


async def cancel(update, context):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_conversation_handler():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft),
            MessageHandler(filters.VOICE, handle_voice_draft),
        ],
        states={
            STATE_AWAITING_APPROVAL: [
                CallbackQueryHandler(callback_approval, pattern="^post_(redo|edit|publish)$"),
            ],
            STATE_AWAITING_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, apply_edit),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        name="post_flow",
        persistent=False,
        # per_message=True нельзя: при нём все хендлеры должны быть CallbackQueryHandler,
        # у нас entry_points и apply_edit — MessageHandler, fallback — CommandHandler.
    )
