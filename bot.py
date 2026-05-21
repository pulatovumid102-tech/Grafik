import logging
import asyncio

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
# TASK MODE
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

    lines.append("• Trading checklistga qaradingmi? ☑️")

    if not user_state["russ"]:
        lines.append("• Russ tili - dars qildingmi? ☑️")

    if not user_state["kitob"]:
        lines.append("• Kitob oqidingmi? ☑️")

    if not user_state["soz"]:
        lines.append("• Rus tilida yangi so'zlar yodladingmi? ☑️")

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

    # OLD REMINDER DELETE
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
# BUTTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global last_reminder_message_id
    global waiting_for_task
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

    # ASOSIY TASKS
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

    # NEW TASK
    if waiting_for_task:

        extra_tasks.append(text)

        waiting_for_task = False

        await update.message.reply_text(
            f"Vazifa qo‘shildi ✅\n\n• {text}"
        )

# =========================
# MENU
# =========================

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "📋 Aktual checklist",
                callback_data="aktual"
            )
        ],

        [
            InlineKeyboardButton(
                "➕ Vazifa qo‘shish",
                callback_data="add_task"
            )
        ]
    ])

    await update.message.reply_text(
        "Menu:",
        reply_markup=keyboard
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
    # EVERY 1 MINUTE
    # =========================

    context.job_queue.run_repeating(
        send_reminder,
        interval=60,
        first=1
    )

    await update.message.reply_text(
        "Bot ishga tushdi ✅\n\n/menu ni yozing"
    )

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
# CALLBACKS
# =========================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global waiting_for_task

    query = update.callback_query

    await query.answer()

    data = query.data

    # AKTUAL CHECKLIST
    if data == "aktual":

        checklist_text = build_message()

        sent_message = await query.message.chat.send_message(
            checklist_text
        )

        await asyncio.sleep(60)

        try:
            await sent_message.delete()
        except:
            pass

        return

    # ADD TASK
    if data == "add_task":

        waiting_for_task = True

        sent_message = await query.message.chat.send_message(
            "Yangi vazifani yuboring ✍️"
        )

        await asyncio.sleep(60)

        try:
            await sent_message.delete()
        except:
            pass

        return

    # MAIN BUTTONS
    await buttons(update, context)

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
        CommandHandler("menu", menu)
    )

    app.add_handler(
        CallbackQueryHandler(callbacks)
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
