from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = "8780693245:AAF8w_cxMTHyr0xHrQnGotDyZrYlfIzj97Q"

counter = 0
running = False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot ishladi")


async def counter_loop(context: ContextTypes.DEFAULT_TYPE):
    global counter

    if counter % 2 == 0:
        text = f"{counter // 2}.3"
    else:
        text = str((counter // 2) + 1)

    counter += 1

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=text
    )


async def start_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running

    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name("counter")

    for job in jobs:
        job.schedule_removal()

    counter_job = context.job_queue.run_repeating(
        counter_loop,
        interval=30,
        first=1,
        chat_id=chat_id,
        name="counter"
    )

    running = True

    await update.message.reply_text("🚀 Sanash boshlandi")


async def stop_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name("counter")

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 To'xtatildi")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("start_count", start_count))
    app.add_handler(CommandHandler("stop_count", stop_count))

    print("Bot ishladi ✅")

    app.run_polling()


if __name__ == "__main__":
    main()
