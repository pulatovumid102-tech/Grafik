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

# TEST uchun:
# har minut reminder

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

    if not user_state["trading"]:
        lines.append("Trading checklistga qaradingmi?")

    if not user_state["russ"]:
        lines.append("Russ tilidan bitta dars organdingmi?")

    if not user_state["kitob"]:
        lines.append("Kitob oqidingmi?")

    if not user_state["soz"]:
        lines.append("Yangi sozlar yodladingmi?")

    # TEST rejimda doim chiqadi
    lines.append("Sirlyda hammasi yaxshimi?")

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    if not user_state["trading"]:
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
                "Sozlar yodlandi",
                callback_data="soz"
            )
        ])

    # Sirly har doim chiqadi
    buttons.append([
        InlineKeyboardButton(
            "Ha hammasi yaxshi",
            callback_data="sirly"
        )
    ])

    return InlineKeyboardMarkup(buttons)

# =========================
# REMINDER
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

    # BUTTON REMOVE
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    if data == "trading":
        user_state["trading"] = True

    elif data == "russ":
        user_state["russ"] = True

    elif data == "kitob":
        user_state["kitob"] = True

    elif data == "soz":
        user_state["soz"] = True

    elif data == "sirly":

        await query.message.reply_text(
            "Rahmat 🙂"
        )

        return

    await query.message.reply_text(
        "Qabul qilindi ✅"
    )

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    # RESET
    user_state["trading"] = False
    user_state["russ"] = False
    user_state["kitob"] = False
    user_state["soz"] = False

    # REMINDER LOOP
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

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
