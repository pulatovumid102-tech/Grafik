from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import asyncio

TOKEN = "8780693245:AAENyEtQ2DDidajLdDaOeKuZKg0nniGI4zw"

CHAT_ID = -5076135815


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Grafik nazorat boti ishga tushdi."
    )


# Reminder yuborish
async def send_graphic_reminder(context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Grafik tekshirildi",
                callback_data="checked"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await context.bot.send_message(
        chat_id=CHAT_ID,
        text="📊 Grafikni tekshirish vaqti bo‘ldi.",
        reply_markup=reply_markup
    )

    # Oldingi statusni reset qilamiz
    context.bot_data["confirmed"] = False

    # 2 minut kutadi
    await asyncio.sleep(120)

    # Agar hali tasdiqlanmagan bo‘lsa
    if context.bot_data.get("confirmed") is False:

        warning = await context.bot.send_message(
            chat_id=CHAT_ID,
            text="⚠️ Grafik hali tekshirilmagan."
        )

        # Warning ID saqlanadi
        context.bot_data["warning_id"] = warning.message_id


# Tugma bosilganda
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    # confirmed status
    context.bot_data["confirmed"] = True

    # old warningni o‘chirish
    warning_id = context.bot_data.get("warning_id")

    if warning_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat.id,
                message_id=warning_id
            )
        except:
            pass

    await query.message.reply_text(
        "Grafik nazorati o‘z vaqtida bajarildi."
    )


def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # Har 15 minut reminder
    app.job_queue.run_repeating(
        send_graphic_reminder,
        interval=900,
        first=5
    )

    print("🔥 Bot ishlayapti")

    app.run_polling()


if __name__ == "__main__":
    main()
