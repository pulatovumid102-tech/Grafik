from datetime import time
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

TOKEN = "8780693245:AAF8w_cxMTHyr0xHrQnGotDyZrYlfIzj97Q"

START_HOUR = 5
END_HOUR = 22

followup_jobs = {}


# =========================
# MAIN REMINDER
# =========================

async def send_main_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    # eski follow-up ni o'chirish
    if chat_id in followup_jobs:
        old_job = followup_jobs[chat_id]
        old_job.schedule_removal()
        del followup_jobs[chat_id]

    text = (
        "📊 Grafikga qara\n\n"
        "📐 Faqat fibo bo‘lsa kirgin\n\n"
        "📋 Hamma instrumentni tekshirib chiq\n\n"
        "⏳ 5 minutda habar olaman"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )

    # 5 minutdan keyin follow-up
    job = context.job_queue.run_once(
        send_followup,
        when=30,
        chat_id=chat_id,
        name=f"followup_{chat_id}"
    )

    followup_jobs[chat_id] = job


# =========================
# FOLLOWUP
# =========================

async def send_followup(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    keyboard = [
        [
            InlineKeyboardButton("✅ Ҳа", callback_data="done"),
            InlineKeyboardButton("❌ Йўқ", callback_data="no"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text="❓ Tekshirdingmi?",
        reply_markup=reply_markup
    )


# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id

    # HA
    if query.data == "done":
        await query.message.reply_text("👍")

    # YO'Q
    elif query.data == "no":
        await query.message.reply_text(
            "⏳ Tekshir, yana 5 minutdan keyin yozaman."
        )

        # eski follow-up ni o'chirish
        if chat_id in followup_jobs:
            old_job = followup_jobs[chat_id]
            old_job.schedule_removal()

        # yangi 5 minutlik follow-up
        job = context.job_queue.run_once(
            send_followup,
            when=30,
            chat_id=chat_id,
            name=f"followup_{chat_id}"
        )

        followup_jobs[chat_id] = job


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Har 20 minut
    context.job_queue.run_repeating(
        send_main_reminder,
        interval=30,
        first=1,
        chat_id=chat_id,
        name=f"main_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Bot ishga tushdi\n\n"
        "⏰ Ish vaqti: 05:00 → 22:00\n"
        "🔁 Har 20 minut reminder keladi"
    )


# =========================
# MAIN
# =========================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot ishladi ✅")

    app.run_polling()


if __name__ == "__main__":
    main()
