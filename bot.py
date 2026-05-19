#!/usr/bin/env python3
"""
Simple Telegram Support Bot
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("Bot ishlayapti 😄🔥")


def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
