from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = "8780693245:AAF8w_cxMTHyr0xHrQnGotDyZrYlfIzj97Q"

counter = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot ishladi")


async def send_numbers(context: ContextTypes.DEFAULT_TYPE):
    global counter

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=str(counter)
    )

    counter += 1


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.job_queue.run_repeating(
        send_numbers,
        interval=10,
        first=1,
        chat_id=update.effective_chat.id,
    )

    await update.message.reply_text("🚀 Sanash boshlandi")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("count", count))

    print("Bot ishladi ✅")

    app.run_polling()


if __name__ == "__main__":
    main()
