import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
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
# HAR 30 DAQIQA
# =========================

REMINDER_INTERVAL = 1800

# =========================
# USER STATE
# =========================

user_state = {
    "russ": False,
    "kitob": False,
    "soz": False,
}

# =========================
# EXTRA TASKS
# =========================

extra_tasks = []

# =========================
# TASK MODE
# =========================

waiting_for_task = False

# =========================
# LAST REMINDER
# =========================

last_reminder_message_id = None

# =========================
# VAQT
# =========================

def get_time():

    return datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).strftime("%H:%M")

# =========================
# BUILD MESSAGE
# =========================

def build_message():

    lines = []

    # ASOSIY
    lines.append("Trading checklistga qaradingmi? ☑️")

    if not user_state["russ"]:
        lines.append("Russ tili - dars qildingmi? ☑️")

    if not user_state["kitob"]:
        lines.append("Kitob oqidingmi? ☑️")

    if not user_state["soz"]:
        lines.append("Rus tilida yangi so'zlar yodladingmi? ☑️")

    lines.append("Sirlyda bollardan habar oldingmi? ☑️")

    # EXTRA TASKS
    if extra_tasks:

        lines.append("\nQo‘shimcha vazifalar:")

        for task in extra_tasks:
            lines.append(f"• {task}")

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    # ASOSIY
    buttons.append([
        InlineKeyboardButton(
            "Trading bajarildi ✅",
            callback_data="trading"
        )
    ])

    if not user_state["russ"]:
        buttons.append([
            InlineKeyboardButton(
                "Russ tili bajarildi ✅",
                callback_data="russ"
            )
        ])

    if not user_state["kitob"]:
        buttons.append([
            InlineKeyboardButton(
                "Kitob oqildi ✅",
                callback_data="kitob"
            )
        ])

    if not user_state["soz"]:
        buttons.append([
            InlineKeyboardButton(
                "So'zlar yodlandi ✅",
                callback_data="soz"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "Sirlydan habar olindi ✅",
            callback_data="sirly"
        )
    ])

    # EXTRA TASK BUTTONLAR
    for index, task in enumerate(extra_tasks):

        buttons.append([
            InlineKeyboardButton(
                f"✅ {task}",
                callback_data=f"task_{index}"
            )
        ])

    return InlineKeyboardMarkup(buttons)

# =========================
# SEND REMINDER
# =========================

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id

    current_hour = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).hour

    # FAQAT 06:00 → 20:00
    if current_hour < 6 or current_hour >= 20:
        return

    # ESKI REMINDERNI O‘CHIRISH
    if last_reminder_message_id:

        try:
            await context.bot.delete_message(
                chat_id=CHAT_ID,
                message_id=last_reminder_message_id
            )
        except:
            pass

    text = build_message()

    keyboard = build_buttons()

    sent_message = await context.bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard
    )

    # OXIRGI MESSAGE ID
    last_reminder_message_id = sent_message.message_id

# =========================
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id

    query = update.callback_query

    await query.answer()

    data = query.data

    # REMINDERNI O‘CHIRISH
    try:
        await query.message.delete()
    except:
        pass

    last_reminder_message_id = None

    time_now = get_time()

    # =========================
    # EXTRA TASK COMPLETE
    # =========================

    if data.startswith("task_"):

        index = int(data.split("_")[1])

        if index < len(extra_tasks):

            completed_task = extra_tasks.pop(index)

            await query.message.chat.send_message(
                f"{completed_task} ✅ {time_now}"
            )

        return

    # =========================
    # ASOSIY
    # =========================

    if data == "trading":

        await query.message.chat.send_message(
            f"Trading checklistga qaraldi ✅ {time_now}"
        )

    elif data == "russ":

        user_state["russ"] = True

        await query.message.chat.send_message(
            f"Russ tili bajarildi ✅ {time_now}"
        )

    elif data == "kitob":

        user_state["kitob"] = True

        await query.message.chat.send_message(
            f"Kitob oqildi ✅ {time_now}"
        )

    elif data == "soz":

        user_state["soz"] = True

        await query.message.chat.send_message(
            f"So'zlar yodlandi ✅ {time_now}"
        )

    elif data == "sirly":

        await query.message.chat.send_message(
            f"Sirlyda hammasi yaxshi ✅ {time_now}"
        )

# =========================
# MESSAGE HANDLER
# =========================

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global waiting_for_task

    text = update.message.text

    # =========================
    # TASK QO‘SHISH
    # =========================

    if text == "➕ Vazifa qo‘shish":

        waiting_for_task = True

        await update.message.reply_text(
            "Yangi vazifani yuboring ✍️"
        )

        return

    # =========================
    # TASK TEXT
    # =========================

    if waiting_for_task:

        extra_tasks.append(text)

        waiting_for_task = False

        await update.message.reply_text(
            f"Vazifa qo‘shildi ✅\n\n• {text}"
        )

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id

    last_reminder_message_id = None

    # PASTDA DOIM TURADI
    menu_keyboard = ReplyKeyboardMarkup(
        [["➕ Vazifa qo‘shish"]],
        resize_keyboard=True
    )

    # AGAR JOB BOR BO‘LSA
    existing_jobs = context.job_queue.get_jobs_by_name(
        "reminder"
    )

    if existing_jobs:

        await update.message.reply_text(
            "Bot allaqachon ishlayapti ✅",
            reply_markup=menu_keyboard
        )

        return

    # YANGI LOOP
    context.job_queue.run_repeating(
        send_reminder,
        interval=REMINDER_INTERVAL,
        first=5,
        name="reminder"
    )

    await update.message.reply_text(
        "Bot ishga tushdi ✅",
        reply_markup=menu_keyboard
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
        "Bot to‘xtatildi 🛑"
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

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            messages
        )
    )

    print("Bot ishladi ✅")

    app.run_polling()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
