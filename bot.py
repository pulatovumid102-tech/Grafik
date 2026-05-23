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
# SETTINGS
# =========================

settings = {
    "start_hour": 6,
    "end_hour": 21,
    "interval": 30,
}

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
# SETTINGS STATE
# =========================

waiting_for_start_hour = False
waiting_for_end_hour = False

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
# REBUILD JOBS
# =========================

def rebuild_jobs(context):

    jobs = context.job_queue.jobs()

    for job in jobs:
        job.schedule_removal()

    start_hour = settings["start_hour"]
    end_hour = settings["end_hour"]
    interval = settings["interval"]

    for hour in range(start_hour, end_hour + 1):

        minute = 0

        while minute < 60:

            if hour == end_hour and minute > 0:
                break

            context.job_queue.run_daily(
                send_reminder,

                time=datetime.strptime(
                    f"{hour}:{minute:02}",
                    "%H:%M"
                ).time().replace(
                    tzinfo=ZoneInfo("Asia/Tashkent")
                ),

                name=f"reminder_{hour}_{minute}"
            )

            minute += interval

# =========================
# BUILD MESSAGE
# =========================

def build_message():

    lines = []

    lines.append("Doimiy vazifalar:\n")

    today = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).weekday()

    # TRADING
    if today not in [5, 6]:

        lines.append(
            "• Trading checklistga qaradingmi? ☑️"
        )

    # SPORT
    lines.append(
        "• Sport bilan shug‘ullandingmi? ☑️"
    )

    # RUSS
    if not user_state["russ"]:

        lines.append(
            "• Russ tili - dars qildingmi? ☑️"
        )

    # KITOB
    if not user_state["kitob"]:

        lines.append(
            "• Kitob oqidingmi? ☑️"
        )

    # SOZ
    if not user_state["soz"]:

        lines.append(
            "• Rus tilida yangi so'zlar yodladingmi? ☑️"
        )

    # SIRLY
    lines.append(
        "• Sirlyda bollardan habar oldingmi? ☑️"
    )

    # EXTRA TASKS
    if extra_tasks:

        lines.append(
            "\nQo‘shimcha vazifalar:\n"
        )

        for task in extra_tasks:

            lines.append(
                f"• {task} ☑️"
            )

    return "\n\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons():

    buttons = []

    today = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).weekday()

    # TRADING
    if today not in [5, 6]:

        buttons.append([
            InlineKeyboardButton(
                "Trading bajarildi ✅",
                callback_data="trading"
            )
        ])

    # SPORT
    buttons.append([
        InlineKeyboardButton(
            "Sport bajarildi ✅",
            callback_data="sport"
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

async def send_reminder(
    context: ContextTypes.DEFAULT_TYPE
):

    global last_reminder_message_id

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

    last_reminder_message_id = (
        sent_message.message_id
    )

# =========================
# SETTINGS MENU
# =========================

async def settings_menu(update, context):

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⏰ Ish vaqti",
                callback_data="settings_time"
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 Xabar oralig‘i",
                callback_data="settings_interval"
            )
        ]
    ])

    if hasattr(update, "message") and update.message:

        await update.message.reply_text(
            "⚙️ Sozlamalar",
            reply_markup=keyboard
        )

    else:

        await update.callback_query.message.reply_text(
            "⚙️ Sozlamalar",
            reply_markup=keyboard
        )

# =========================
# BUTTON HANDLER
# =========================

async def buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global last_reminder_message_id
    global extra_tasks
    global waiting_for_start_hour
    global waiting_for_end_hour

    query = update.callback_query

    await query.answer()

    data = query.data

    time_now = get_time()

    # SETTINGS TIME
    if data == "settings_time":

        waiting_for_start_hour = True

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("05:00", callback_data="start_5"),
                InlineKeyboardButton("06:00", callback_data="start_6"),
                InlineKeyboardButton("07:00", callback_data="start_7"),
            ]
        ])

        await query.message.reply_text(
            "Start vaqtni tanlang",
            reply_markup=keyboard
        )

        return

    # START HOUR
    if data.startswith("start_"):

        start_hour = int(data.split("_")[1])

        settings["start_hour"] = start_hour

        waiting_for_start_hour = False
        waiting_for_end_hour = True

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("20:00", callback_data="end_20"),
                InlineKeyboardButton("21:00", callback_data="end_21"),
                InlineKeyboardButton("22:00", callback_data="end_22"),
            ]
        ])

        await query.message.reply_text(
            "Tugash vaqtni tanlang",
            reply_markup=keyboard
        )

        return

    # END HOUR
    if data.startswith("end_"):

        end_hour = int(data.split("_")[1])

        settings["end_hour"] = end_hour

        rebuild_jobs(context)

        await query.message.reply_text(
            f"✅ O‘zgartirish qabul qilindi\n\n"
            f"Ish vaqti:\n"
            f"{settings['start_hour']}:00 → "
            f"{settings['end_hour']}:00"
        )

        return

    # INTERVAL SETTINGS
    if data == "settings_interval":

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("10 minut", callback_data="interval_10"),
                InlineKeyboardButton("20 minut", callback_data="interval_20"),
            ],
            [
                InlineKeyboardButton("30 minut", callback_data="interval_30"),
                InlineKeyboardButton("1 soat", callback_data="interval_60"),
            ]
        ])

        await query.message.reply_text(
            "Xabar oralig‘ini tanlang",
            reply_markup=keyboard
        )

        return

    # INTERVAL SAVE
    if data.startswith("interval_"):

        interval = int(data.split("_")[1])

        settings["interval"] = interval

        rebuild_jobs(context)

        await query.message.reply_text(
            f"✅ O‘zgartirish qabul qilindi\n\n"
            f"Har {interval} minutda reminder yuboriladi"
        )

        return

    # DELETE REMINDER
    try:

        await query.message.delete()

    except:
        pass

    last_reminder_message_id = None

    # EXTRA TASK COMPLETE
    if data.startswith("task_"):

        index = int(
            data.split("_")[1]
        )

        if index < len(extra_tasks):

            completed_task = (
                extra_tasks.pop(index)
            )

            await query.message.chat.send_message(
                f"{completed_task} ✅ {time_now}"
            )

        return

    # MAIN TASKS
    if data == "trading":

        await query.message.chat.send_message(
            f"Trading checklistga qaraldi ✅ {time_now}"
        )

    elif data == "sport":

        await query.message.chat.send_message(
            f"Sport bajarildi ✅ {time_now}"
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

async def messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global waiting_for_task
    global extra_tasks

    text = update.message.text

    # AKTUAL CHECKLIST
    if "Aktual checklist" in text:

        checklist_text = build_message()

        await update.message.reply_text(
            checklist_text,
            reply_markup=build_buttons()
        )

        return

    # ADD TASK
    if "Vazifa qo‘shish" in text:

        waiting_for_task = True

        await update.message.reply_text(
            "Yangi vazifani yuboring ✍️"
        )

        return

    # SETTINGS
    if "Sozlamalar" in text:

        await settings_menu(update, context)

        return

    # BOT HAQIDA
    if "Bot haqida" in text:

        await update.message.reply_text(
            f"ℹ️ Bot haqida\n\n"
            f"⏰ Ish vaqti: "
            f"{settings['start_hour']}:00 - "
            f"{settings['end_hour']}:00\n"
            f"🔁 Interval: har "
            f"{settings['interval']} daqiqa\n\n"
            f"Bot belgilangan vaqtlarda "
            f"checklist yuboradi."
        )

        return

    # NEW TASK
    if waiting_for_task:

        extra_tasks.append(text)

        waiting_for_task = False

        await update.message.reply_text(
            f"Vazifa qo‘shildi ✅\n\n• {text}"
        )

# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global last_reminder_message_id

    last_reminder_message_id = None

    rebuild_jobs(context)

    # MENU
    keyboard = ReplyKeyboardMarkup(
        [
            ["📋 Aktual checklist"],
            ["➕ Vazifa qo‘shish"],
            ["⚙️ Sozlamalar"],
            ["ℹ️ Bot haqida"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"Bot ishga tushdi ✅\n\n"
        f"Bot sizga belgilangan vaqtlarda "
        f"checklist yuboradi.\n\n"
        f"⏰ Ish vaqti: "
        f"{settings['start_hour']}:00 - "
        f"{settings['end_hour']}:00\n"
        f"🔁 Interval: har "
        f"{settings['interval']} daqiqa\n\n"
        f"⚙️ Sozlamalar orqali:\n"
        f"• ish vaqtini\n"
        f"• intervalni\n"
        f"o‘zgartirishingiz mumkin.",
        reply_markup=keyboard
    )

# =========================
# STOP
# =========================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

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
