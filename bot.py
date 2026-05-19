from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import pytz
from datetime import datetime

TOKEN = "8780693245:AAENyEtQ2DDidajLdDaOeKuZKg0nniGI4zw"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot ishlayapti 😄🔥")


async def send_graphic_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = 1645167548

    current_time = datetime.now(
        pytz.timezone("Asia/Tashkent")
    ).strftime("%H:%M")

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📊 Grafikni tekshirish vaqti bo'ldi\n⏰ {current_time}"
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    job_queue = app.job_queue

    job_queue.run_repeating(
        send_graphic_reminder,
        interval=60,
        first=5
    )

    print("Bot ishga tushdi 🚀")

    app.run_polling()


if __name__ == "__main__":
    main()
