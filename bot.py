import logging
from datetime import datetime
from zoneinfo import ZoneInfo

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

TOKEN = "8780693245:AAGEbojMC_6WodZtHRvYG52EVTic8BB2x7c"

# =========================
# CHAT ID
# =========================

CHAT_ID = 1645167548

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# TEST / REAL
# =========================

# TEST:
# REMINDER_INTERVAL = 10

# REAL:
REMINDER_INTERVAL = 900

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

    # HAR DOIM
    lines.append("Trading checklistga qaradingmi? ☑️")

    if not user_state["russ"]:
        lines.append("Russ tili - dars qildingmi? ☑️")

    if not user_state["kitob"]:
        lines.append("Kitob oqidingmi? ☑️")

    if not user_state["soz"]:
        lines.append("Rus tilida yangi sozlar yodladingmi? ☑️")

    # HAR DOIM
    lines.append("Sirlyda bollardan habar oldingmi? ☑️")

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    buttons.append([
        InlineKeyboardButton(
            "Trading bajarildi",
            callback_data="trading"
        )
    ])

    if not user_state["russ"]:
        buttons.append([
            InlineKeyboardButton(
                "Russ tili bajarildi",
                callback_data="russ"
            )
        ])

    if not user_state["kitob"]:
        buttons.append([
            InlineKeyboardButton(
                "Kitob oqildi",
                callback_data="kitob"
            )
        ])

    if not user_state["soz"]:
        buttons.append([
            InlineKeyboardButton(
                "So'zlar yodlandi",
                callback_data="soz"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "Sirlydan habar olindi",
            callback_data="sirly"
        )
    ])

    return InlineKeyboardMarkup(buttons)

# =========================
# SEND REMINDER
# =========================

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):

    print("REMINDER ISHLADI")

    current_hour = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).hour

    # FAQAT 06:00 → 20:00
    if current_hour < 6 or current_hour >= 20:
        print("HOZIR DAM OLISH VAQTI")
        return

    text = build_message()

    keyboard = build_buttons()

    try:

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            reply_markup=keyboard
        )

        print("XABAR YUBORILDI ✅")

    except Exception as e:

        print(f"XATO: {e}")

# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    # ESKI REMINDERNI OCHIRISH
    try:
        await query.message.delete()
    except:
        pass

    # Trading
    if data == "trading":

        await query.message.chat.send_message(
            "📊 Trading checklistga qaraldi"
        )

    # Russ
    elif data == "russ":

        user_state["russ"] = True

        await query.message.chat.send_message(
            "🇷🇺 Russ tili bajarildi"
        )

    # Kitob
    elif data == "kitob":

        user_state["kitob"] = True

        await query.message.chat.send_message(
            "📘 Kitob oqildi"
        )

    # Sozlar
    elif data == "soz":

        user_state["soz"] = True

        await query.message.chat.send_message(
            "🧠 So'zlar yodlandi"
        )

    # Sirly
    elif data == "sirly":

        await query.message.chat.send_message(
            "🤝 Sirlyda hammasi yaxshi"
        )

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # RESET
    user_state["russ"] = False
    user_state["kitob"] = False
    user_state["soz"] = False

    # ESKI JOBLARNI TOPISH
    old_jobs = context.job_queue.get_jobs_by_name(
        "reminder"
    )

    # ESKI JOBLARNI OCHIRISH
    if old_jobs:
        for job in old_jobs:
            job.schedule_removal()

    # LOOP
    context.job_queue.run_repeating(
        send_reminder,
        interval=REMINDER_INTERVAL,
        first=5,
        name="reminder"
    )

    await update.message.reply_text(
        "Bot ishga tushdi ✅"
    )

# =========================
# STOP
# =========================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):

    jobs = context.job_queue.get_jobs_by_name(
        "reminder"
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
