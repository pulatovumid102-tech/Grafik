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
# WAITING TASK
# =========================

waiting_for_task = False

# =========================
# LAST REMINDER
# =========================

last_reminder_message_id = None

# =========================
# TIME
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

    lines.append("Doimiy vazifalar:\n")

    # TRADING
    lines.append("• Trading checklistga qaradingmi? ☑️")

    # RUSS
    if not user_state["russ"]:
        lines.append("• Russ tili - dars qildingmi? ☑️")

    # KITOB
    if not user_state["kitob"]:
        lines.append("• Kitob oqidingmi? ☑️")

    # SOZ
    if not user_state["soz"]:
        lines.append("• Rus tilida yangi so'zlar yodladingmi? ☑️")

    # SIRLY
    lines.append("• Sirlyda bollardan habar oldingmi? ☑️")

    # EXTRA TASKS
    if extra_tasks:

        lines.append("\nQo‘shimcha vazifalar:\n")

        for task in extra_tasks:
            lines.append(f"• {task} ☑️")

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    # TRADING
    buttons.append([
        InlineKeyboardButton(
            "Trading bajarildi ✅",
            callback_data="trading"
        )
    ])

    # RUSS
    if not user_state["russ"]:

        buttons.append([
            InlineKeyboardButton(
                "Russ tili bajarildi ✅",
                callback_data="russ"
            )
        ])

    # KITOB
    if not user_state["kitob"]:

        buttons.append([
            InlineKeyboardButton(
                "Kitob oqildi ✅",
                callback_data="kitob"
            )
        ])

    # SOZ
    if not user_state["soz"]:

        buttons.append([
            InlineKeyboardButton(
                "So'zlar yodlandi ✅",
                callback_data="soz"
            )
        ])

    # SIRLY
    buttons.append([
        InlineKeyboardButton(
            "Sirlydan habar olindi ✅",
            callback_data="sirly"
        )
    ])

    # EXTRA TASKS
    for index, task in enumerate(extra_tasks):

        buttons.append([
            InlineKeyboardButton(
                f"{task} ✅",
                callback_data=f"task_{index}"
            )
        ])

    return InlineKeyboardMarkup(buttons)

# =========================
# SEND REMINDER
# =========================

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id

    # DELETE OLD REMINDER
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

    last_reminder_message_id = sent_message.message_id

# =========================
# BUTTON HANDLER
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id
    global extra_tasks

    query = update.callback_query

    await query.answer()

    data = query.data

    time_now = get_time()

    # DELETE REMINDER
    try:
        await query.message.delete()
    except:
        pass

    last_reminder_message_id = None

    # EXTRA TASK COMPLETE
    if data.startswith("task_"):

        index = int(data.split("_")[1])

        if index < len(extra_tasks):

            completed_task = extra_tasks.pop(index)

            await query.message.chat.send_message(
                f"{completed_task} ✅ {time_now}"
            )

        return

    # MAIN TASKS
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
    global extra_tasks

    text = update.message.text

    # =========================
    # AKTUAL CHECKLIST
    # =========================

    if text == "📋 Aktual checklist":

        checklist_text = build_message()

        await update.message.reply_text(
            checklist_text,
            reply_markup=build_buttons()
        )

        return

    # =========================
    # ADD TASK
    # =========================

    if text == "➕ Vazifa qo‘shish":

        waiting_for_task = True

        await update.message.reply_text(
            "Yangi vazifani yuboring ✍️"
        )

        return

    # =========================
    # NEW TASK
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

    # REMOVE OLD JOBS
    old_jobs = context.job_queue.jobs()

    for job in old_jobs:
        job.schedule_removal()

    # =========================
    # 06:00 → 21:00
    # HAR 30 DAQIQA
    # =========================

    for hour in range(6, 22):

        # :00
        context.job_queue.run_daily(
            send_reminder,
            time=datetime.strptime(
                f"{hour}:00",
                "%H:%M"
            ).time(),
            name=f"reminder_{hour}_00"
        )

        # :30
        if hour != 21:

            context.job_queue.run_daily(
                send_reminder,
                time=datetime.strptime(
                    f"{hour}:30",
                    "%H:%M"
                ).time(),
                name=f"reminder_{hour}_30"
            )

    # =========================
    # MENU
    # =========================

    keyboard = ReplyKeyboardMarkup(
        [
            ["📋 Aktual checklist"],
            ["➕ Vazifa qo‘shish"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "Bot ishga tushdi ✅",
        reply_markup=keyboard
    )

    # FIRST CHECKLIST
    await send_reminder(context)

# =========================
# STOP
# =========================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):

    jobs = context.job_queue.jobs()

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
