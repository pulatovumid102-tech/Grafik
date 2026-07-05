"""
Sirly Mini-App uchun Telegram bot.

Vazifasi:
  - index.html (mini-app) Supabase'ga yozib qo'yadigan xabar/eslatma/fayl
    so'rovlarini muntazam tekshirib, Telegram orqali yetkazib beradi.
  - Uchta jadval kuzatiladi:
      1) bot_group_messages  -> umumiy guruhga (GROUP_CHAT_ID) xabar
      2) bot_reminders       -> aniq foydalanuvchiga (chat_id) belgilangan
                                 vaqtda eslatma (sekretar, kaiten budilnik)
      3) file_send_requests  -> Hujjatlar bo'limidan foydalanuvchiga
                                 xabar yoki fayl yuborish

Ishga tushirish:
  1) pip install -r requirements.txt
  2) .env.example'ni .env qilib nusxalab, qiymatlarni to'ldiring
  3) python bot.py
"""

import os
import logging
from datetime import datetime, timezone, time as dt_time
from zoneinfo import ZoneInfo

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ============================================================
# SOZLAMALAR — to'g'ridan-to'g'ri shu yerga yozilgan
# (Railway'da Variables qo'shish shart emas, lekin xohlasangiz
#  pastdagi os.environ.get(...) orqali Variables bilan ustidan
#  yozib qo'yish ham mumkin — hozircha shart emas)
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8693834890:AAFs3rg_ZTlu1hOc0rBm9zgjD1az-R2xr_c")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qtrniovpkrwimeohamkc.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF0cm5pb3Zwa3J3aW1lb2hhbWtjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwMTY4NjUsImV4cCI6MjA5NjU5Mjg2NX0.j4gUqZlqMHR0ltIMCDB-UfWPvuPVs9B9HF0If2fPxhU")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "-5531952742"))
SUPPORT_GROUP_ID = -5417855498
MINIAPP_URL = os.environ.get("MINIAPP_URL", "https://pulatovumid102-tech.github.io/Grafik/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "20"))
MUAMMOLI_MUDDAT_SOAT = 24
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("sirly-bot")

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

http_client: httpx.AsyncClient | None = None


# ============================================================
# SUPABASE YORDAMCHI FUNKSIYALAR
# ============================================================
async def sb_get(table: str, params: dict) -> list:
    resp = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params
    )
    resp.raise_for_status()
    return resp.json()


async def sb_patch(table: str, row_id: str, data: dict) -> None:
    resp = await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**SB_HEADERS, "Prefer": "return=minimal"},
        params={"id": f"eq.{row_id}"},
        json=data,
    )
    resp.raise_for_status()


async def claim_row(table: str, row_id: str) -> bool:
    """Faqat hozir ham 'pending' bo'lgan qatorni 'processing'ga o'tkazadi.
    Agar boshqa bot nusxasi allaqachon shu qatorni band qilgan bo'lsa,
    bu funksiya False qaytaradi va biz uni qayta yubormaymiz.
    Shu orqali bir nechta bot nusxasi bir vaqtda ishlasa ham,
    xabar hech qachon IKKI MARTA yuborilmaydi."""
    resp = await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**SB_HEADERS, "Prefer": "return=representation"},
        params={"id": f"eq.{row_id}", "status": "eq.pending"},
        json={"status": "processing"},
    )
    resp.raise_for_status()
    claimed_rows = resp.json()
    return len(claimed_rows) > 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 1) GURUHGA XABARLAR — bot_group_messages
# ============================================================
async def process_group_messages(app: Application) -> None:
    try:
        rows = await sb_get(
            "bot_group_messages",
            params={
                "status": "eq.pending",
                "or": f"(send_at.is.null,send_at.lte.{now_iso()})",
                "order": "created_at.asc",
                "limit": str(BATCH_LIMIT),
            },
        )
    except Exception as e:
        log.error("bot_group_messages fetch xato: %s", e)
        return

    for row in rows:
        row_id = row.get("id")
        try:
            if not await claim_row("bot_group_messages", row_id):
                continue  # boshqa bot nusxasi allaqachon oldi
            text = row.get("text") or ""
            if not text.strip():
                await sb_patch("bot_group_messages", row_id, {"status": "failed"})
                continue
            target_chat_id = row.get("chat_id") or GROUP_CHAT_ID
            await app.bot.send_message(chat_id=target_chat_id, text=text)
            await sb_patch("bot_group_messages", row_id, {"status": "sent"})
            log.info("Guruhga yuborildi: %s -> chat_id=%s", row_id, target_chat_id)
        except Exception as e:
            log.error("Guruhga yuborishda xato (%s): %s", row_id, e)
            try:
                await sb_patch("bot_group_messages", row_id, {"status": "failed"})
            except Exception:
                pass


# ============================================================
# 2) SHAXSIY ESLATMALAR — bot_reminders
# (sekretar uchrashuvlari, kaiten budilnik)
# ============================================================
async def process_reminders(app: Application) -> None:
    try:
        rows = await sb_get(
            "bot_reminders",
            params={
                "status": "eq.pending",
                "remind_at": f"lte.{now_iso()}",
                "order": "remind_at.asc",
                "limit": str(BATCH_LIMIT),
            },
        )
    except Exception as e:
        log.error("bot_reminders fetch xato: %s", e)
        return

    for row in rows:
        row_id = row.get("id")
        try:
            if not await claim_row("bot_reminders", row_id):
                continue  # boshqa bot nusxasi allaqachon oldi
            chat_id = row.get("chat_id")
            text = row.get("text") or ""
            if not chat_id or not text.strip():
                await sb_patch("bot_reminders", row_id, {"status": "failed"})
                continue
            await app.bot.send_message(chat_id=chat_id, text=text)
            await sb_patch("bot_reminders", row_id, {"status": "sent"})
            log.info("Eslatma yuborildi: %s -> chat_id=%s", row_id, chat_id)
        except Exception as e:
            log.error("Eslatma yuborishda xato (%s): %s", row_id, e)
            try:
                await sb_patch("bot_reminders", row_id, {"status": "failed"})
            except Exception:
                pass


# ============================================================
# 3) HUJJAT/XABAR YUBORISH SO'ROVLARI — file_send_requests
# (Hujjatlar bo'limidagi "📤 Yuborish" tugmasi)
# ============================================================
async def process_file_requests(app: Application) -> None:
    try:
        rows = await sb_get(
            "file_send_requests",
            params={
                "status": "eq.pending",
                "order": "created_at.asc",
                "limit": str(BATCH_LIMIT),
            },
        )
    except Exception as e:
        log.error("file_send_requests fetch xato: %s", e)
        return

    for row in rows:
        row_id = row.get("id")
        try:
            if not await claim_row("file_send_requests", row_id):
                continue  # boshqa bot nusxasi allaqachon oldi
            chat_id = row.get("chat_id")
            kind = row.get("kind")
            if not chat_id:
                await sb_patch("file_send_requests", row_id, {"status": "failed"})
                continue

            if kind == "file" and row.get("file_url"):
                await app.bot.send_document(
                    chat_id=chat_id,
                    document=row["file_url"],
                    filename=row.get("file_name") or None,
                )
            elif row.get("message_text"):
                await app.bot.send_message(chat_id=chat_id, text=row["message_text"])
            else:
                await sb_patch("file_send_requests", row_id, {"status": "failed"})
                continue

            await sb_patch("file_send_requests", row_id, {"status": "sent"})
            log.info("Fayl/xabar so'rovi bajarildi: %s -> chat_id=%s", row_id, chat_id)
        except Exception as e:
            log.error("Fayl/xabar yuborishda xato (%s): %s", row_id, e)
            try:
                await sb_patch("file_send_requests", row_id, {"status": "failed"})
            except Exception:
                pass


# ============================================================
# MUAMMOLI MIJOZLAR — davriy tekshiruv xabari (10:15 dan 23:30 gacha,
# har 15 daqiqada), ikki mustaqil tasdiqlash tugmasi bilan
# ============================================================
def generate_check_times() -> list:
    times = []
    start_minutes = 10 * 60 + 15
    end_minutes = 23 * 60 + 30
    cur = start_minutes
    while cur <= end_minutes:
        h, m = divmod(cur, 60)
        times.append(dt_time(hour=h, minute=m, tzinfo=TASHKENT_TZ))
        cur += 15
    return times


def build_check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Admin panelda hammasi joyida", callback_data="muammoli_check:admin")],
        [InlineKeyboardButton("Telegramda ham hammasi joyida", callback_data="muammoli_check:tg")],
    ])


async def muammoli_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    time_label = datetime.now(TASHKENT_TZ).strftime("%H:%M")
    text = (
        f"🔎 TEKSHIRUV — {time_label}\n"
        "📋 Admin panelga qarang — murojaat qilgan muammoli mijoz yo'qmi?\n"
        "👥 Hamkorlar bilan ochilgan telegram guruhlarga qarang — murojaat qilgan hamkor yo'qmi?"
    )
    try:
        await app.bot.send_message(chat_id=SUPPORT_GROUP_ID, text=text, reply_markup=build_check_keyboard())
        log.info("Tekshiruv xabari yuborildi (%s)", time_label)
    except Exception as e:
        log.error("Tekshiruv xabarini yuborishda xato: %s", e)


async def muammoli_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = (query.data or "").split(":", 1)
    btn_type = parts[1] if len(parts) == 2 else ""
    if btn_type not in ("admin", "tg"):
        return

    current_markup = query.message.reply_markup
    still_present = False
    new_rows = []
    if current_markup:
        for row in current_markup.inline_keyboard:
            new_row = [btn for btn in row if btn.callback_data != query.data]
            if len(new_row) != len(row):
                still_present = True
            if new_row:
                new_rows.append(new_row)

    if not still_present:
        return  # allaqachon boshqa kishi tomonidan tasdiqlangan

    user = query.from_user
    name = user.full_name
    username = user.username or ""
    who = f"{name} (@{username})" if username else name
    time_label = datetime.now(TASHKENT_TZ).strftime("%H:%M")

    if btn_type == "admin":
        line = f"✅ {who} — {time_label} holatida admin panelda javob berilmagan murojaat yo'qligini tasdiqladi."
    else:
        line = f"✅ {who} — {time_label} holatida hamkorlar guruhlarida javob berilmagan murojaat yo'qligini tasdiqladi."

    new_text = (query.message.text or "") + "\n\n" + line
    new_markup = InlineKeyboardMarkup(new_rows) if new_rows else None

    try:
        await query.edit_message_text(text=new_text, reply_markup=new_markup)
    except Exception as e:
        log.error("Tekshiruv xabarini tahrirlashda xato: %s", e)


# ============================================================
# MUAMMOLI MIJOZLAR — kunlik eslatma va muddat nazorati
# ============================================================
def collect_support_usernames(org_nodes: list) -> list:
    """Org struktura ичida 'Support bo'limi' nomli tugunni topib,
    uning barcha farzand tugunlaridan (bo'sh bo'lmagan tg maydoni bilan)
    Telegram username'larini yig'ib qaytaradi."""
    if not isinstance(org_nodes, list):
        return []
    support_ids = [
        n.get("id") for n in org_nodes
        if "support" in (n.get("name") or "").lower()
    ]
    if not support_ids:
        return []
    by_parent = {}
    for n in org_nodes:
        by_parent.setdefault(n.get("parentId"), []).append(n)

    usernames = []
    def walk(node_id):
        for child in by_parent.get(node_id, []):
            tg = (child.get("tg") or "").strip()
            if tg:
                usernames.append(tg.lstrip("@"))
            walk(child.get("id"))

    for sid in support_ids:
        walk(sid)
    return list(dict.fromkeys(usernames))


async def daily_muammoli_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.muammoli_mijozlar"})
        muammoli_data = rows[0]["data"] if rows else {}
        items = muammoli_data.get("items", []) if isinstance(muammoli_data, dict) else []
        open_items = [
            it for it in items
            if not it.get("archived") and it.get("holati") != "hal_qilindi"
        ]

        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        usernames = collect_support_usernames(org_nodes)

        time_label = datetime.now(TASHKENT_TZ).strftime("%H:%M")
        lines = [f"🔔 KUNLIK ESLATMA — Support bo'limiga — {time_label}"]

        if not open_items:
            lines.append("✅ Muammoli mijozlar yo'q")
        else:
            lines.append(f"⚠️ Hozircha muammoli mijozlarda {len(open_items)} ta ochiq murojaat bor:")
            lines.append("")
            for i, it in enumerate(open_items, start=1):
                restoran = it.get("restoran") or it.get("sababchiIchki") or "—"
                ism = it.get("ism", "—")
                tel = it.get("tel", "")
                turi = it.get("turi", "Boshqa")
                days = "?"
                created_at = it.get("createdAt")
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        days = max(0, (datetime.now(timezone.utc) - created_dt).days)
                    except Exception:
                        pass
                header = f"{i}. {restoran} — {ism}" + (f" ({tel})" if tel else "")
                lines.append(header)
                lines.append(f"   {turi} — {days} kun kutmoqda")
            if usernames:
                tags = " ".join(f"@{u}" for u in usernames)
                lines.append("")
                lines.append(f"👥 Support bo'limi: {tags}")

        await app.bot.send_message(chat_id=SUPPORT_GROUP_ID, text="\n".join(lines))
        log.info("Kunlik muammoli eslatma yuborildi (%s)", time_label)
    except Exception as e:
        log.error("Kunlik muammoli eslatma xatosi: %s", e)


async def check_overdue_muammoli(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.muammoli_mijozlar"})
        if not rows:
            return
        muammoli_data = rows[0]["data"]
        if not isinstance(muammoli_data, dict):
            return
        items = muammoli_data.get("items", [])
        changed = False
        for it in items:
            if it.get("archived") or it.get("holati") == "hal_qilindi":
                continue
            if it.get("overdueNotified"):
                continue
            created_at = it.get("createdAt")
            if not created_at:
                continue
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                continue
            hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
            if hours >= MUAMMOLI_MUDDAT_SOAT:
                text = (
                    "⏰ MUDDAT O'TDI (24 soat)!\n"
                    f"🏪 Restoran: {it.get('restoran', '—')}\n"
                    f"🙋 Mijoz: {it.get('ism', '—')}\n"
                    f"📋 Turi: {it.get('turi', 'Boshqa')}\n"
                    "Iltimos, tezroq hal qiling!"
                )
                await app.bot.send_message(chat_id=SUPPORT_GROUP_ID, text=text)
                it["overdueNotified"] = True
                changed = True
        if changed:
            await sb_patch("biznes_data", "muammoli_mijozlar", {"data": muammoli_data})
            log.info("Muddati o'tgan murojaat(lar) uchun ogohlantirish yuborildi")
    except Exception as e:
        log.error("Muddat tekshirish xatosi: %s", e)


# ============================================================
# DAVRIY TEKSHIRUV (JobQueue)
# ============================================================
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    await process_group_messages(app)
    await process_reminders(app)
    await process_file_requests(app)


# ============================================================
# /start BUYRUG'I — mini-appni ochish tugmasi
# ============================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if MINIAPP_URL:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📋 Ilovani ochish", web_app=WebAppInfo(url=MINIAPP_URL))]]
        )
        await update.message.reply_text(
            "Xush kelibsiz! Ilovani ochish uchun tugmani bosing:", reply_markup=kb
        )
    else:
        await update.message.reply_text("Bot ishga tushdi. MINIAPP_URL sozlanmagan.")


# ============================================================
# ISHGA TUSHIRISH / TO'XTATISH
# ============================================================
async def post_init(app: Application) -> None:
    global http_client
    http_client = httpx.AsyncClient(timeout=30)
    log.info("Sirly bot ishga tushdi. Poll interval: %s soniya", POLL_SECONDS)


async def post_shutdown(app: Application) -> None:
    if http_client:
        await http_client.aclose()


def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(muammoli_check_callback, pattern="^muammoli_check:"))
    app.job_queue.run_repeating(poll_job, interval=POLL_SECONDS, first=5)

    # Muammoli mijozlar — davriy tekshiruv xabari, 10:15 dan 23:30 gacha har 15 daqiqada
    for check_time in generate_check_times():
        app.job_queue.run_daily(muammoli_check_job, time=check_time)

    # Muammoli mijozlar — kunlik eslatma, har kuni 10:30, 15:00, 19:00 (Toshkent vaqti)
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=10, minute=30, tzinfo=TASHKENT_TZ))
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=15, minute=0, tzinfo=TASHKENT_TZ))
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=19, minute=0, tzinfo=TASHKENT_TZ))

    # Muammoli mijozlar — 24 soatlik muddat nazorati, har 30 daqiqada tekshiriladi
    app.job_queue.run_repeating(check_overdue_muammoli, interval=1800, first=60)

    log.info("Bot polling boshlandi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
