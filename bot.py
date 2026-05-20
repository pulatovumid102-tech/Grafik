import logging
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

# =========================
# TOKEN
# =========================

TOKEN = "8780693245:AAF8w_cxMTHyr0xHrQnGotDyZrYlfIzj97Q"

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# TEST REJIM
# =========================

# HAR MINUT XABAR KELADI
REMINDER_INTERVAL = 60

# =========================
# USER STATE
# =========================

user_state = {
    "russ": False,
    "kitob": False,
    "soz": False,
}

# =========================
# BUILD MESSAGE
# =========================

def build_message():

    lines = []

    # Trading HAR DOIM chiqadi
    lines.append("Trading checklistga qaradingmi? ☑️")

    # Russ tili
    if not user_state["russ"]:
        lines.append("Russ tili - dars qildingmi? ☑️")

    # Kitob
    if not user_state["kitob"]:
        lines.append("Kitob oqidingmi? ☑️")

    # Sozlar
    if not user_state["soz"]:
        lines.append("Rus tilida yangi sozlar yodladingmi?")

    # Sirly HAR DOIM chiqadi
    lines.append("Sirlyda bollardan habar oldingmi?")

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    # Trading HAR DOIM chiqadi
    buttons.append([
        InlineKeyboardButton(
            "Trading bajarildi",
            callback_data="trading"
        )
    ])

    # Russ tili
    if not user_state["russ"]:
        buttons.append([
            InlineKeyboardButton(
                "Russ tili bajarildi",
                callback_data="russ"
            )
        ])

    # Kitob
    if not user_state["kitob"]:
        buttons.append([
            InlineKeyboardButton(
                "Kitob oqildi",
                callback_data="kitob"
            )
        ])

    # Sozlar
    if not user_state["soz"]:
        buttons.append([
            InlineKeyboardButton(
                "Sozlar yodlandi",
                callback_data="soz"
            )
        ])

    # Sirly HAR DOIM chiqadi
    buttons.append([
        InlineKeyboardButton(
            "Ha hammasi yaxshi",
            callback_data="sirly"
        )
    ])

    return InlineKeyboardMarkup(buttons)

# =========================
# SEND REMINDER
# =========================

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):

    text = build_message()

    keyboard = build_buttons()

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=text,
        reply_markup=keyboard
    )

# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    # BUTTONLARNI OCHIRISH
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    # Trading
    if data == "trading":

        await query.message.reply_text(
            "Trading checklistga qaraldi ✅"
        )

    # Russ tili
    elif data == "russ":

        user_state["russ"] = True

        await query.message.reply_text(
            "Russ tili bajarildi ✅"
        )

    # Kitob
    elif data == "kitob":

        user_state["kitob"] = True

        await query.message.reply_text(
            "Kitob oqildi ✅"
        )

    # Sozlar
    elif data == "soz":

        user_state["soz"] = True

        await query.message.reply_text(
            "So'zlar yodlandi ✅"
        )

    # Sirly
    elif data == "sirly":

        await query.message.reply_text(
            "Sirlyda hammasi yaxshi ✅"
        )

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    # RESET
    user_state["russ"] = False
    user_state["kitob"] = False
    user_state["soz"] = False

    # OLD JOBLARNI OCHIRISH
    old_jobs = context.job_queue.get_jobs_by_name(
        f"reminder_{chat_id}"
    )

    for job in old_jobs:
        job.schedule_removal()

    # LOOP
    context.job_queue.run_repeating(
        send_reminder,
        interval=REMINDER_INTERVAL,
        first=1,
        chat_id=chat_id,
        name=f"reminder_{chat_id}"
    )

    await update.message.reply_text(
        "Bot ishga tushdi ✅\n\n"
        "TEST rejim: har minut reminder keladi"
    )

# =========================
# STOP
# =========================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(
        f"reminder_{chat_id}"
    )

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text(
        "Bot toxtatildi 🛑"
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
        CommandHandler("stop", stop)
    )

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    print("Bot ishladi ✅")

    app.run_polling()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
