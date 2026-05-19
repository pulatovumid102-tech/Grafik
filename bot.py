import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("8780693245:AAENyEtQ2DDidajLdDaOeKuZKg0nniGI4zw")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot ishladi ✅")


async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Grafikni tekshir\n\n❗️Trendni va riskni tekshir"
    )


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="📊 Grafikni tekshir\n\n❗️Trendni va riskni tekshir"
    )


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    context.job_queue.run_repeating(
        send_reminder,
        interval=60,
        first=5,
        chat_id=chat_id,
        name=str(chat_id),
    )

    await update.message.reply_text("⏰ Endi har 1 minutda eslatma yuboraman")


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grafik", grafik))
    app.add_handler(CommandHandler("timer", set_timer))

    print("Bot ishladi ✅")
    app.run_polling()


if __name__ == "__main__":
    main()
