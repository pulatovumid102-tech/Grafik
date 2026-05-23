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
            },
            "last_reminder_message_id": None,
            "waiting_for_task": False,
            "settings_msg_ids": [],
            "settings_chat_id": None,
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

    today = datetime.now(
        ZoneInfo("Asia/Tashkent")
    ).weekday()

    # TAKRORLANUVCHI
    takror_items = []
    if today not in [5, 6]:
        takror_items.append("Trading - grafikga qara")
    takror_items.append("Sirly - hammasi yaxshimi tekshir")

    # KUNLIK
    kunlik_all = [
        ("sport", "Sport"),
        ("russ",  "Til"),
        ("kitob", "Kitob"),
    ]

    kunlik_items = [
        label for key, label in kunlik_all
        if not u["user_state"][key]
    ]

    done_count = sum(
        1 for key, _ in kunlik_all
        if u["user_state"][key]
    )

    # PROGRESS (faqat kunlik vazifalar)
    total   = len(kunlik_all)
    done    = done_count
    percent = int((done / total) * 100) if total > 0 else 0

    # BUILD TEXT
    lines = []

    lines.append("📋 CHECKLIST")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("• Takrorlanuvchi")
    lines.append("")
    for i, item in enumerate(takror_items, 1):
        lines.append(f"{i}\ufe0f\u20e3 {item}")

    if kunlik_items:
        lines.append("━━━━━━━━━━━━━━")
        lines.append("• Kunlik vazifalar")
        lines.append("")
        for i, item in enumerate(kunlik_items, 1):
            lines.append(f"{i}. {item}")

    if u["extra_tasks"]:
        lines.append("━━━━━━━━━━━━━━")
        lines.append("• Qo'shimcha vazifalar")
        lines.append("")
        for i, task in enumerate(u["extra_tasks"], 1):
            lines.append(f"{i}. {task}")



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
                "Trading - grafikga qaradim ✅",
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
                "Sport bilan shug'ullandim ✅",
                callback_data="sport"
            )
        ])

    # RUSS
    if not u["user_state"]["russ"]:

        buttons.append([
            InlineKeyboardButton(
                "Til o'rgandim ✅",
                callback_data="russ"
            )
        ])

    # KITOB
    if not u["user_state"]["kitob"]:

        buttons.append([
            InlineKeyboardButton(
                "Kitob o'qidim ✅",
                callback_data="kitob"
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

        sent = await update.message.reply_text(
            text,
            reply_markup=keyboard
        )

        u = get_user(update.message.from_user.id)
        u["settings_msg_ids"] = [sent.message_id]
        u["settings_chat_id"] = sent.chat_id

    else:

        sent = await update.callback_query.message.reply_text(
            text,
            reply_markup=keyboard
        )

        u = get_user(update.callback_query.from_user.id)
        u["settings_msg_ids"] = [sent.message_id]
        u["settings_chat_id"] = sent.chat_id

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

        sent = await query.message.reply_text(
            "Start vaqtni tanlang",
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

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

        sent = await query.message.reply_text(
            "Tugash vaqtni tanlang",
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # END HOUR
    if data.startswith("end_"):

        end_hour = int(data.split("_")[1])

        u["settings"]["end_hour"] = end_hour

        rebuild_jobs(context, user_id)

        sent = await query.message.reply_text(
            f"✅ O'zgartirish qabul qilindi\n\n"
            f"Ish vaqti:\n"
            f"{u['settings']['start_hour']}:00 → "
            f"{u['settings']['end_hour']}:00\n\n"
            f"⏱ Yuborilgan xabarlar 5 soniyada o'chiriladi"
        )

        u["settings_msg_ids"].append(sent.message_id)

        _chat_id = u.get("settings_chat_id", user_id)
        _msg_ids = list(u["settings_msg_ids"])

        async def delete_all_end(ctx):
            for mid in _msg_ids:
                try:
                    await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                except:
                    pass

        context.job_queue.run_once(delete_all_end, when=5, data=None)

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

        sent = await query.message.reply_text(
            "Xabar oralig'ini tanlang",
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # INTERVAL SAVE
    if data.startswith("interval_"):

        interval = int(data.split("_")[1])

        u["settings"]["interval"] = interval

        rebuild_jobs(context, user_id)

        sent = await query.message.reply_text(
            f"✅ O'zgartirish qabul qilindi\n\n"
            f"Har {interval} minutda reminder yuboriladi\n\n"
            f"⏱ Yuborilgan xabarlar 5 soniyada o'chiriladi"
        )

        u["settings_msg_ids"].append(sent.message_id)

        _chat_id = u.get("settings_chat_id", user_id)
        _msg_ids = list(u["settings_msg_ids"])

        async def delete_all_interval(ctx):
            for mid in _msg_ids:
                try:
                    await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                except:
                    pass

        context.job_queue.run_once(delete_all_interval, when=5, data=None)

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

        text_msg = build_message(user_id) + "\n\n⏱ Xabar 60 soniyada o'chiriladi"

        sent = await update.message.reply_text(
            text_msg,
            reply_markup=build_buttons(user_id)
        )

        _chat_id = sent.chat_id
        _msg_id = sent.message_id

        async def delete_checklist(ctx):
            try:
                await ctx.bot.delete_message(
                    chat_id=_chat_id,
                    message_id=_msg_id
                )
            except:
                pass

        context.job_queue.run_once(
            delete_checklist,
            when=60,
            data=None,
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
        "🛑 Bot checklist yuborishni to'xtatdi
"
        "▶️ Qayta boshlash uchun /start bosing"
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
