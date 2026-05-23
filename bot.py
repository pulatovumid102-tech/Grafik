import logging
import json
import os

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
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# TASKS FOLDER
# =========================

TASKS_FOLDER = "user_tasks"

os.makedirs(TASKS_FOLDER, exist_ok=True)

# =========================
# USER DATA (per user)
# =========================

user_data = {}

def get_user(user_id):

    if user_id not in user_data:

        user_data[user_id] = {
            "extra_tasks": load_tasks(user_id),
            "user_state": {
                "sport": False,
                "russ": False,
                "kitob": False,
                "soz": False,
            },
            "last_reminder_message_id": None,
            "waiting_for_task": False,
            "settings": {
                "start_hour": 6,
                "end_hour": 21,
                "interval": 30,
            },
        }

    return user_data[user_id]

# =========================
# LOAD TASKS
# =========================

def load_tasks(user_id):

    path = os.path.join(
        TASKS_FOLDER,
        f"tasks_{user_id}.json"
    )

    try:

        with open(path, "r") as file:
            return json.load(file)

    except:
        return []

# =========================
# SAVE TASKS
# =========================

def save_tasks(user_id, tasks):

    path = os.path.join(
        TASKS_FOLDER,
        f"tasks_{user_id}.json"
    )

    with open(path, "w") as file:

        json.dump(
            tasks,
            file,
            ensure_ascii=False,
            indent=4
        )

# =========================
# TIME
# =========================

def get_time():

    return datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).strftime("%H:%M")

# =========================
# RESET USER STATE (kunlik)
# =========================

async def reset_user_state(
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = context.job.data

    u = get_user(user_id)

    u["user_state"]["sport"] = False
    u["user_state"]["russ"] = False
    u["user_state"]["kitob"] = False
    u["user_state"]["soz"] = False

    logging.info(
        f"user_state reset qilindi: {user_id}"
    )

# =========================
# REBUILD JOBS
# =========================

def rebuild_jobs(context, user_id):

    # Faqat shu userni joblarini o'chir
    jobs = context.job_queue.jobs()

    for job in jobs:

        if job.data == user_id:
            job.schedule_removal()

    u = get_user(user_id)

    start_hour = u["settings"]["start_hour"]
    end_hour = u["settings"]["end_hour"]
    interval = u["settings"]["interval"]

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

                name=f"reminder_{user_id}_{hour}_{minute}",
                data=user_id,
                chat_id=user_id,
            )

            minute += interval

    # Reset job: har kuni 00:00
    context.job_queue.run_daily(
        reset_user_state,

        time=datetime.strptime(
            "00:00",
            "%H:%M"
        ).time().replace(
            tzinfo=ZoneInfo("Asia/Tashkent")
        ),

        name=f"reset_{user_id}",
        data=user_id,
        chat_id=user_id,
    )

# =========================
# BUILD MESSAGE
# =========================

def build_message(user_id):

    u = get_user(user_id)

    lines = []

    # TAKRORLANUVCHI VAZIFALAR (har doim ko'rinadi)
    lines.append("🔁 Takrorlanuvchi vazifalar:\n")

    today = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).weekday()

    # TRADING — har doim (dushanbadan jumagacha)
    if today not in [5, 6]:

        lines.append(
            "• Trading checklistga qaradingmi? ☑️"
        )

    # SIRLY — har doim
    lines.append(
        "• Sirlyda bollardan habar oldingmi? ☑️"
    )

    # KUNLIK VAZIFALAR (bajarilsa yakunlanadi)
    kunlik_lines = []

    # SPORT
    if not u["user_state"]["sport"]:
        kunlik_lines.append(
            "• Sport bilan shug'ullandingmi? ☑️"
        )

    # RUSS
    if not u["user_state"]["russ"]:
        kunlik_lines.append(
            "• Russ tili - dars qildingmi? ☑️"
        )

    # KITOB
    if not u["user_state"]["kitob"]:
        kunlik_lines.append(
            "• Kitob oqidingmi? ☑️"
        )

    # SOZ
    if not u["user_state"]["soz"]:
        kunlik_lines.append(
            "• Rus tilida yangi so'zlar yodladingmi? ☑️"
        )

    if kunlik_lines:
        lines.append("\n✅ Kunlik vazifalar:\n")
        lines.extend(kunlik_lines)
    else:
        lines.append("\n✅ Kunlik vazifalar: barchasi bajarildi! 🎉")

    # EXTRA TASKS
    if u["extra_tasks"]:

        lines.append(
            "\nQo'shimcha vazifalar:\n"
        )

        for task in u["extra_tasks"]:

            lines.append(
                f"• {task} ☑️"
            )

    return "\n".join(lines)

# =========================
# BUILD BUTTONS
# =========================

def build_buttons(user_id):

    u = get_user(user_id)

    buttons = []

    today = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).weekday()

    # TAKRORLANUVCHI — har doim ko'rinadi

    # TRADING
    if today not in [5, 6]:

        buttons.append([
            InlineKeyboardButton(
                "Trading bajarildi ✅",
                callback_data="trading"
            )
        ])

    # SIRLY — har doim
    buttons.append([
        InlineKeyboardButton(
            "Sirlydan habar olindi ✅",
            callback_data="sirly"
        )
    ])

    # KUNLIK — bajarilsa yashirinadi

    # SPORT
    if not u["user_state"]["sport"]:

        buttons.append([
            InlineKeyboardButton(
                "Sport bajarildi ✅",
                callback_data="sport"
            )
        ])

    # RUSS
    if not u["user_state"]["russ"]:

        buttons.append([
            InlineKeyboardButton(
                "Russ tili bajarildi ✅",
                callback_data="russ"
            )
        ])

    # KITOB
    if not u["user_state"]["kitob"]:

        buttons.append([
            InlineKeyboardButton(
                "Kitob oqildi ✅",
                callback_data="kitob"
            )
        ])

    # SOZ
    if not u["user_state"]["soz"]:

        buttons.append([
            InlineKeyboardButton(
                "So'zlar yodlandi ✅",
                callback_data="soz"
            )
        ])

    # EXTRA TASKS
    for index, task in enumerate(u["extra_tasks"]):

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

    user_id = context.job.data

    u = get_user(user_id)

    # Eski xabarni o'chir
    if u["last_reminder_message_id"]:

        try:

            await context.bot.delete_message(
                chat_id=user_id,
                message_id=u["last_reminder_message_id"]
            )

        except:
            pass

    text = build_message(user_id)

    keyboard = build_buttons(user_id)

    sent_message = await context.bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=keyboard
    )

    u["last_reminder_message_id"] = (
        sent_message.message_id
    )

# =========================
# SETTINGS MENU
# =========================

async def settings_menu(update, context, user_id):

    u = get_user(user_id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⏰ Ish vaqti",
                callback_data="settings_time"
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 Xabar oralig'i",
                callback_data="settings_interval"
            )
        ]
    ])

    text = (
        f"⚙️ Sozlamalar\n\n"
        f"Joriy holat:\n"
        f"⏰ {u['settings']['start_hour']}:00 → "
        f"{u['settings']['end_hour']}:00\n"
        f"🔁 Har {u['settings']['interval']} daqiqa"
    )

    if hasattr(update, "message") and update.message:

        await update.message.reply_text(
            text,
            reply_markup=keyboard
        )

    else:

        await update.callback_query.message.reply_text(
            text,
            reply_markup=keyboard
        )

# =========================
# BUTTON HANDLER
# =========================

async def buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    u = get_user(user_id)

    data = query.data

    time_now = get_time()

    # SETTINGS TIME
    if data == "settings_time":

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

        u["settings"]["start_hour"] = start_hour

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

        u["settings"]["end_hour"] = end_hour

        rebuild_jobs(context, user_id)

        await query.message.reply_text(
            f"✅ O'zgartirish qabul qilindi\n\n"
            f"Ish vaqti:\n"
            f"{u['settings']['start_hour']}:00 → "
            f"{u['settings']['end_hour']}:00"
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
            "Xabar oralig'ini tanlang",
            reply_markup=keyboard
        )

        return

    # INTERVAL SAVE
    if data.startswith("interval_"):

        interval = int(data.split("_")[1])

        u["settings"]["interval"] = interval

        rebuild_jobs(context, user_id)

        await query.message.reply_text(
            f"✅ O'zgartirish qabul qilindi\n\n"
            f"Har {interval} minutda "
            f"reminder yuboriladi"
        )

        return

    # DELETE REMINDER
    try:

        await query.message.delete()

    except:
        pass

    u["last_reminder_message_id"] = None

    # EXTRA TASK COMPLETE
    if data.startswith("task_"):

        index = int(data.split("_")[1])

        if index < len(u["extra_tasks"]):

            completed_task = u["extra_tasks"].pop(index)

            save_tasks(user_id, u["extra_tasks"])

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

        u["user_state"]["sport"] = True

        await query.message.chat.send_message(
            f"Sport bajarildi ✅ {time_now}"
        )

    elif data == "russ":

        u["user_state"]["russ"] = True

        await query.message.chat.send_message(
            f"Russ tili bajarildi ✅ {time_now}"
        )

    elif data == "kitob":

        u["user_state"]["kitob"] = True

        await query.message.chat.send_message(
            f"Kitob oqildi ✅ {time_now}"
        )

    elif data == "soz":

        u["user_state"]["soz"] = True

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

    user_id = update.message.from_user.id

    u = get_user(user_id)

    text = update.message.text

    # AKTUAL CHECKLIST
    if "Aktual checklist" in text:

        await update.message.reply_text(
            build_message(user_id),
            reply_markup=build_buttons(user_id)
        )

        return

    # ADD TASK
    if "Vazifa qo'shish" in text:

        u["waiting_for_task"] = True

        await update.message.reply_text(
            "Yangi vazifani yuboring ✍️"
        )

        return

    # SETTINGS
    if "Sozlamalar" in text:

        await settings_menu(update, context, user_id)

        return

    # BOT HAQIDA
    if "Bot haqida" in text:

        await update.message.reply_text(
            f"ℹ️ Bot haqida\n\n"
            f"⏰ Ish vaqti: "
            f"{u['settings']['start_hour']}:00 - "
            f"{u['settings']['end_hour']}:00\n"
            f"🔁 Interval: har "
            f"{u['settings']['interval']} daqiqa\n\n"
            f"Bot belgilangan vaqtlarda "
            f"checklist yuboradi."
        )

        return

    # NEW TASK
    if u["waiting_for_task"]:

        u["extra_tasks"].append(text)

        save_tasks(user_id, u["extra_tasks"])

        u["waiting_for_task"] = False

        await update.message.reply_text(
            f"Vazifa qo'shildi ✅\n\n• {text}"
        )

        return

# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.message.from_user.id

    u = get_user(user_id)

    u["last_reminder_message_id"] = None

    rebuild_jobs(context, user_id)

    keyboard = ReplyKeyboardMarkup(
        [
            ["📋 Aktual checklist"],
            ["➕ Vazifa qo'shish"],
            ["⚙️ Sozlamalar"],
            ["ℹ️ Bot haqida"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"Bot ishga tushdi ✅\n\n"
        f"⏰ Ish vaqti: "
        f"{u['settings']['start_hour']}:00 - "
        f"{u['settings']['end_hour']}:00\n"
        f"🔁 Interval: har "
        f"{u['settings']['interval']} daqiqa\n\n"
        f"⚙️ Sozlamalar orqali:\n"
        f"• ish vaqtini\n"
        f"• intervalni\n"
        f"o'zgartirishingiz mumkin.",
        reply_markup=keyboard
    )

# =========================
# STOP
# =========================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.message.from_user.id

    jobs = context.job_queue.jobs()

    for job in jobs:

        if job.data == user_id:
            job.schedule_removal()

    await update.message.reply_text(
        "Bot to'xtatildi 🛑"
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
