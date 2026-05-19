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

# active joblarni saqlash
main_jobs = {}
followup_jobs = {}


# =========================
# MAIN REMINDER
# =========================

async def send_main_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    # eski followupni ochirish
    if chat_id in followup_jobs:
        old_job = followup_jobs[chat_id]
        old_job.schedule_removal()
        del followup_jobs[chat_id]

    text = (
        "📊 Grafikga qara\n\n"
        "📐 Faqat fibo bolsa kirgin\n\n"
        "📋 Hamma instrumentni tekshirib chiq\n\n"
        "⏳ 5 minutda habar olaman"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )

    # TEST UCHUN 10 SEKUND
    job = context.job_queue.run_once(
        send_followup,
        when=10,
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
            InlineKeyboardButton(
                "✅ Ha",
                callback_data="done"
            ),

            InlineKeyboardButton(
                "❌ Yoq",
                callback_data="no"
            ),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text="❓ Tekshirdingmi?",
        reply_markup=reply_markup
    )

    # agar user javob bermasa
    auto_job = context.job_queue.run_once(
        auto_no,
        when=10,
        chat_id=chat_id,
        name=f"auto_no_{chat_id}"
    )

    followup_jobs[chat_id] = auto_job


# =========================
# AUTO NO
# =========================

async def auto_no(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ Javob kelmadi.\n\nYana 5 minutdan keyin yozaman."
    )

    # yana followup
    job = context.job_queue.run_once(
        send_followup,
        when=10,
        chat_id=chat_id,
        name=f"followup_{chat_id}"
    )

    followup_jobs[chat_id] = job


# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()

    chat_id = query.message.chat.id

    # active followupni ochirish
    if chat_id in followup_jobs:
        old_job = followup_jobs[chat_id]
        old_job.schedule_removal()
        del followup_jobs[chat_id]

    # HA
    if query.data == "done":

        await query.message.reply_text("👍")

    # YOQ
    elif query.data == "no":

        await query.message.reply_text(
            "⏳ Tekshir, yana 5 minutdan keyin yozaman."
        )

        # yangi followup
        job = context.job_queue.run_once(
            send_followup,
            when=10,
            chat_id=chat_id,
            name=f"followup_{chat_id}"
        )

        followup_jobs[chat_id] = job


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # eski main jobni ochirish
    if chat_id in main_jobs:
        old_main = main_jobs[chat_id]
        old_main.schedule_removal()
        del main_jobs[chat_id]

    # eski followupni ochirish
    if chat_id in followup_jobs:
        old_follow = followup_jobs[chat_id]
        old_follow.schedule_removal()
        del followup_jobs[chat_id]

    # yangi main scheduler
    main_job = context.job_queue.run_repeating(
        send_main_reminder,
        interval=60,
        first=0,
        chat_id=chat_id,
        name=f"main_{chat_id}"
    )

    main_jobs[chat_id] = main_job

    await update.message.reply_text(
        "✅ Bot ishga tushdi\n\n"
        "🔁 Test rejim ishlayapti"
    )


# =========================
# MAIN
# =========================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    print("Bot ishladi ✅")

    app.run_polling()


if __name__ == "__main__":
    main()
