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

        default_data = load_user_data(user_id)
        user_data[user_id] = {
            "extra_tasks": default_data["extra_tasks"],
            "takror_tasks": default_data["takror_tasks"],
            "kunlik_tasks": default_data["kunlik_tasks"],
            "user_state": {},
            "last_reminder_message_id": None,
            "waiting_for_task": False,
            "waiting_for_takror_task": False,
            "waiting_for_kunlik_task": False,
            "editing_takror_index": None,
            "editing_kunlik_index": None,
            "settings_msg_ids": [],
            "settings_chat_id": None,
            "settings": {
                "start_hour": 6,
                "end_hour": 21,
                "interval": 30,
            },
        }
        # user_state kunlik_tasks dan dinamik yasaladi
        for task in user_data[user_id]["kunlik_tasks"]:
            user_data[user_id]["user_state"][task["key"]] = False

    return user_data[user_id]

# =========================
# DEFAULT TAKROR TASKS
# =========================

DEFAULT_TAKROR = [
    {"key": "trading", "label": "Trading - grafikga qara", "weekdays_only": True},
    {"key": "sirly",   "label": "Sirly - hammasi yaxshimi tekshir", "weekdays_only": False},
]

DEFAULT_KUNLIK = [
    {"key": "sport", "label": "Sport"},
    {"key": "russ",  "label": "Til"},
    {"key": "kitob", "label": "Kitob"},
]

# =========================
# LOAD USER DATA
# =========================

def load_user_data(user_id):

    path = os.path.join(
        TASKS_FOLDER,
        f"data_{user_id}.json"
    )

    try:

        with open(path, "r") as file:
            data = json.load(file)
            if "takror_tasks" not in data:
                data["takror_tasks"] = DEFAULT_TAKROR[:]
            if "kunlik_tasks" not in data:
                data["kunlik_tasks"] = DEFAULT_KUNLIK[:]
            if "extra_tasks" not in data:
                data["extra_tasks"] = []
            return data

    except:
        return {
            "extra_tasks": [],
            "takror_tasks": DEFAULT_TAKROR[:],
            "kunlik_tasks": DEFAULT_KUNLIK[:],
        }

# =========================
# SAVE USER DATA
# =========================

def save_user_data(user_id):

    u = get_user(user_id)

    path = os.path.join(
        TASKS_FOLDER,
        f"data_{user_id}.json"
    )

    with open(path, "w") as file:

        json.dump(
            {
                "extra_tasks": u["extra_tasks"],
                "takror_tasks": u["takror_tasks"],
                "kunlik_tasks": u["kunlik_tasks"],
            },
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

    for task in u["kunlik_tasks"]:
        u["user_state"][task["key"]] = False

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

    # TAKRORLANUVCHI — dinamik
    takror_items = []
    for t in u["takror_tasks"]:
        if t.get("weekdays_only") and today in [5, 6]:
            continue
        takror_items.append(t["label"])

    # KUNLIK — dinamik
    kunlik_items = [
        t["label"] for t in u["kunlik_tasks"]
        if not u["user_state"].get(t["key"], False)
    ]

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
    for t in u["takror_tasks"]:
        if t.get("weekdays_only") and today in [5, 6]:
            continue
        buttons.append([
            InlineKeyboardButton(
                f"{t['label']} ✅",
                callback_data=f"takror_{t['key']}"
            )
        ])

    # KUNLIK — bajarilsa yashirinadi
    for t in u["kunlik_tasks"]:
        if not u["user_state"].get(t["key"], False):
            buttons.append([
                InlineKeyboardButton(
                    f"{t['label']} ✅",
                    callback_data=f"kunlik_{t['key']}"
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
        ],
        [
            InlineKeyboardButton(
                "📝 Vazifalar",
                callback_data="settings_tasks"
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

        _chat_id = user_id
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

        _chat_id = user_id
        _msg_ids = list(u["settings_msg_ids"])

        async def delete_all_interval(ctx):
            for mid in _msg_ids:
                try:
                    await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                except:
                    pass

        context.job_queue.run_once(delete_all_interval, when=5, data=None)

        return

    # VAZIFALAR MENYUSI
    if data == "settings_tasks":

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Takrorlanuvchi vazifalar", callback_data="tasks_takror")],
            [InlineKeyboardButton("✅ Kunlik vazifalar", callback_data="tasks_kunlik")],
        ])

        sent = await query.message.reply_text(
            "📝 Vazifalar",
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # TAKRORLANUVCHI VAZIFALAR MENYUSI
    if data == "tasks_takror":

        lines = ["\U0001f501 Takrorlanuvchi vazifalar:\n"]
        for i, t in enumerate(u["takror_tasks"], 1):
            lines.append(f"{i}. {t['label']}")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Qo'shish", callback_data="takror_add")],
            [InlineKeyboardButton("🗑 O'chirish", callback_data="takror_delete")],
            [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data="takror_edit")],
        ])

        sent = await query.message.reply_text(
            "\n".join(lines),
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # KUNLIK VAZIFALAR MENYUSI
    if data == "tasks_kunlik":

        lines = ["\u2705 Kunlik vazifalar:\n"]
        for i, t in enumerate(u["kunlik_tasks"], 1):
            lines.append(f"{i}. {t['label']}")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Qo'shish", callback_data="kunlik_add")],
            [InlineKeyboardButton("🗑 O'chirish", callback_data="kunlik_delete")],
            [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data="kunlik_edit")],
        ])

        sent = await query.message.reply_text(
            "\n".join(lines),
            reply_markup=keyboard
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # TAKRORLANUVCHI — QO'SHISH
    if data == "takror_add":

        u["waiting_for_takror_task"] = True

        sent = await query.message.reply_text(
            "Yangi takrorlanuvchi vazifa nomini yuboring ✍️"
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # KUNLIK — QO'SHISH
    if data == "kunlik_add":

        u["waiting_for_kunlik_task"] = True

        sent = await query.message.reply_text(
            "Yangi kunlik vazifa nomini yuboring ✍️"
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # TAKRORLANUVCHI — O'CHIRISH (ro'yxat)
    if data == "takror_delete":

        if not u["takror_tasks"]:
            await query.message.reply_text("Vazifalar yo'q")
            return

        buttons_list = [
            [InlineKeyboardButton(f"{t['label']} ❌", callback_data=f"takror_del_{i}")]
            for i, t in enumerate(u["takror_tasks"])
        ]

        sent = await query.message.reply_text(
            "Qaysi vazifani o'chirish kerak?",
            reply_markup=InlineKeyboardMarkup(buttons_list)
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # KUNLIK — O'CHIRISH (ro'yxat)
    if data == "kunlik_delete":

        if not u["kunlik_tasks"]:
            await query.message.reply_text("Vazifalar yo'q")
            return

        buttons_list = [
            [InlineKeyboardButton(f"{t['label']} ❌", callback_data=f"kunlik_del_{i}")]
            for i, t in enumerate(u["kunlik_tasks"])
        ]

        sent = await query.message.reply_text(
            "Qaysi vazifani o'chirish kerak?",
            reply_markup=InlineKeyboardMarkup(buttons_list)
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # TAKRORLANUVCHI — O'CHIRISH (tasdiqlash)
    if data.startswith("takror_del_"):

        index = int(data.split("_")[2])

        if index < len(u["takror_tasks"]):
            removed = u["takror_tasks"].pop(index)
            save_user_data(user_id)

            sent = await query.message.chat.send_message(
                f"{removed['label']} o'chirildi ✅\n\n⏱ Xabar 5 soniyada o'chiriladi"
            )

            u["settings_msg_ids"].append(sent.message_id)
            _msg_ids = list(u["settings_msg_ids"])

            async def _del_takror_del(ctx):
                for mid in _msg_ids:
                    try:
                        await ctx.bot.delete_message(chat_id=user_id, message_id=mid)
                    except:
                        pass

            context.job_queue.run_once(_del_takror_del, when=5, data=None)

        return

    # KUNLIK — O'CHIRISH (tasdiqlash)
    if data.startswith("kunlik_del_"):

        index = int(data.split("_")[2])

        if index < len(u["kunlik_tasks"]):
            removed = u["kunlik_tasks"].pop(index)
            u["user_state"].pop(removed["key"], None)
            save_user_data(user_id)

            sent = await query.message.chat.send_message(
                f"{removed['label']} o'chirildi ✅\n\n⏱ Xabar 5 soniyada o'chiriladi"
            )

            u["settings_msg_ids"].append(sent.message_id)
            _msg_ids = list(u["settings_msg_ids"])

            async def _del_kunlik_del(ctx):
                for mid in _msg_ids:
                    try:
                        await ctx.bot.delete_message(chat_id=user_id, message_id=mid)
                    except:
                        pass

            context.job_queue.run_once(_del_kunlik_del, when=5, data=None)

        return

    # TAKRORLANUVCHI — NOMINI O'ZGARTIRISH (ro'yxat)
    if data == "takror_edit":

        if not u["takror_tasks"]:
            await query.message.reply_text("Vazifalar yo'q")
            return

        buttons_list = [
            [InlineKeyboardButton(t["label"], callback_data=f"takror_edt_{i}")]
            for i, t in enumerate(u["takror_tasks"])
        ]

        sent = await query.message.reply_text(
            "Qaysi vazifani o'zgartirish kerak?",
            reply_markup=InlineKeyboardMarkup(buttons_list)
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # KUNLIK — NOMINI O'ZGARTIRISH (ro'yxat)
    if data == "kunlik_edit":

        if not u["kunlik_tasks"]:
            await query.message.reply_text("Vazifalar yo'q")
            return

        buttons_list = [
            [InlineKeyboardButton(t["label"], callback_data=f"kunlik_edt_{i}")]
            for i, t in enumerate(u["kunlik_tasks"])
        ]

        sent = await query.message.reply_text(
            "Qaysi vazifani o'zgartirish kerak?",
            reply_markup=InlineKeyboardMarkup(buttons_list)
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # TAKRORLANUVCHI — NOMINI O'ZGARTIRISH (tanlandi)
    if data.startswith("takror_edt_"):

        index = int(data.split("_")[2])

        u["editing_takror_index"] = index

        sent = await query.message.reply_text(
            "Yangi nomini yuboring ✍️"
        )

        u["settings_msg_ids"].append(sent.message_id)

        return

    # KUNLIK — NOMINI O'ZGARTIRISH (tanlandi)
    if data.startswith("kunlik_edt_"):

        index = int(data.split("_")[2])

        u["editing_kunlik_index"] = index

        sent = await query.message.reply_text(
            "Yangi nomini yuboring ✍️"
        )

        u["settings_msg_ids"].append(sent.message_id)

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

    # TAKRORLANUVCHI TASK BOSILDI
    if data.startswith("takror_"):

        key = data[len("takror_"):]

        task = next((t for t in u["takror_tasks"] if t["key"] == key), None)

        if task:
            await query.message.chat.send_message(
                f"{task['label']} ✅ {time_now}"
            )

    # KUNLIK TASK BOSILDI
    elif data.startswith("kunlik_"):

        key = data[len("kunlik_"):]

        task = next((t for t in u["kunlik_tasks"] if t["key"] == key), None)

        if task:
            u["user_state"][key] = True

            await query.message.chat.send_message(
                f"{task['label']} bajarildi ✅ {time_now}"
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

    # TAKRORLANUVCHI VAZIFA QO'SHISH
    if u["waiting_for_takror_task"]:

        import re
        key = "takror_" + re.sub(r"\W+", "_", text.lower())[:20]

        u["takror_tasks"].append({"key": key, "label": text, "weekdays_only": False})
        save_user_data(user_id)
        u["waiting_for_takror_task"] = False

        sent = await update.message.reply_text(
            f"Takrorlanuvchi vazifa qo'shildi \u2705\n\n\u2022 {text}\n\n\u23f1 Xabar 5 soniyada o'chiriladi"
        )

        u["settings_msg_ids"].append(sent.message_id)

        _chat_id = user_id
        _msg_ids = list(u["settings_msg_ids"])

        async def _del_takror_add(ctx):
            for mid in _msg_ids:
                try:
                    await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                except:
                    pass

        context.job_queue.run_once(_del_takror_add, when=5, data=None)

        return

    # KUNLIK VAZIFA QO'SHISH
    if u["waiting_for_kunlik_task"]:

        import re
        key = "kunlik_" + re.sub(r"\W+", "_", text.lower())[:20]

        u["kunlik_tasks"].append({"key": key, "label": text})
        u["user_state"][key] = False
        save_user_data(user_id)
        u["waiting_for_kunlik_task"] = False

        sent = await update.message.reply_text(
            f"Kunlik vazifa qo'shildi \u2705\n\n\u2022 {text}\n\n\u23f1 Xabar 5 soniyada o'chiriladi"
        )

        u["settings_msg_ids"].append(sent.message_id)

        _chat_id = user_id
        _msg_ids = list(u["settings_msg_ids"])

        async def _del_kunlik_add(ctx):
            for mid in _msg_ids:
                try:
                    await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                except:
                    pass

        context.job_queue.run_once(_del_kunlik_add, when=5, data=None)

        return

    # TAKRORLANUVCHI NOMINI O'ZGARTIRISH
    if u["editing_takror_index"] is not None:

        index = u["editing_takror_index"]

        if index < len(u["takror_tasks"]):
            old_label = u["takror_tasks"][index]["label"]
            u["takror_tasks"][index]["label"] = text
            save_user_data(user_id)

            sent = await update.message.reply_text(
                f"Nom o'zgartirildi \u2705\n\n{old_label} \u2192 {text}\n\n\u23f1 Xabar 5 soniyada o'chiriladi"
            )

            u["settings_msg_ids"].append(sent.message_id)

            _chat_id = user_id
            _msg_ids = list(u["settings_msg_ids"])

            async def _del_te(ctx):
                for mid in _msg_ids:
                    try:
                        await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                    except:
                        pass

            context.job_queue.run_once(_del_te, when=5, data=None)

        u["editing_takror_index"] = None

        return

    # KUNLIK NOMINI O'ZGARTIRISH
    if u["editing_kunlik_index"] is not None:

        index = u["editing_kunlik_index"]

        if index < len(u["kunlik_tasks"]):
            old_label = u["kunlik_tasks"][index]["label"]
            u["kunlik_tasks"][index]["label"] = text
            save_user_data(user_id)

            sent = await update.message.reply_text(
                f"Nom o'zgartirildi \u2705\n\n{old_label} \u2192 {text}\n\n\u23f1 Xabar 5 soniyada o'chiriladi"
            )

            u["settings_msg_ids"].append(sent.message_id)

            _chat_id = user_id
            _msg_ids = list(u["settings_msg_ids"])

            async def _del_ke(ctx):
                for mid in _msg_ids:
                    try:
                        await ctx.bot.delete_message(chat_id=_chat_id, message_id=mid)
                    except:
                        pass

            context.job_queue.run_once(_del_ke, when=5, data=None)

        u["editing_kunlik_index"] = None

        return

    # ADD TASK (qo'shimcha)
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

        takror_count = len(u["takror_tasks"])
        kunlik_count = len(u["kunlik_tasks"])
        extra_count  = len(u["extra_tasks"])

        sent = await update.message.reply_text(
            f"\u2139\ufe0f Bot haqida\n\n"
            f"\u23f0 Ish vaqti: "
            f"{u['settings']['start_hour']}:00 - "
            f"{u['settings']['end_hour']}:00\n"
            f"\U0001f501 Interval: har "
            f"{u['settings']['interval']} daqiqa\n\n"
            f"\U0001f4cb Vazifalar soni:\n"
            f"\u2022 Takrorlanuvchi: {takror_count} ta\n"
            f"\u2022 Kunlik: {kunlik_count} ta\n"
            f"\u2022 Qo'shimcha: {extra_count} ta\n\n"
            f"\u2699\ufe0f Sozlamalar orqali:\n"
            f"\u2022 Ish vaqtini o'zgartirish\n"
            f"\u2022 Xabar oralig'ini o'zgartirish\n"
            f"\u2022 Takrorlanuvchi vazifalarni boshqarish\n"
            f"\u2022 Kunlik vazifalarni boshqarish\n\n"
            f"\u23f1 Xabar 120 soniyada o'chiriladi"
        )

        _cid = sent.chat_id
        _mid = sent.message_id

        async def _del_about(ctx):
            try:
                await ctx.bot.delete_message(chat_id=_cid, message_id=_mid)
            except:
                pass

        context.job_queue.run_once(_del_about, when=120, data=None)

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
        "\U0001f6d1 Bot checklist yuborishni to\'xtatdi\n"
        "\u25b6\ufe0f Qayta boshlash uchun /start bosing"
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
