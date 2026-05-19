from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = "8780693245:AAF8w_cxMTHyr0xHrQnGotDyZrYlfIzj97Q"

counter = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot ishga tushdi\n\n/start_count yozing"
    )


async def send_counter(context: ContextTypes.DEFAULT_TYPE):
    global counter

    counter += 1

    if counter % 2 == 1:
        text = f"{counter}.3"
    else:
        text = str(counter // 2)

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=text
    )


async def start_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    context.job_queue.run_repeating(
        send_counter,
        interval=30,
        first=1,
        chat_id=chat_id,
        name=str(chat_id),
    )

    await update.message.reply_text(
        "🚀 Sanash boshlandi"
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("start_count", start_count))

    print("Bot ishladi ✅")

    app.run_polling()


if __name__ == "__main__":
    main()
