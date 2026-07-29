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
import io
from datetime import datetime, timezone, time as dt_time, timedelta
from zoneinfo import ZoneInfo

import httpx
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ============================================================
# SOZLAMALAR — to'g'ridan-to'g'ri shu yerga yozilgan
# (Railway'da Variables qo'shish shart emas, lekin xohlasangiz
#  pastdagi os.environ.get(...) orqali Variables bilan ustidan
#  yozib qo'yish ham mumkin — hozircha shart emas)
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8693834890:AAHMcQyOmv2bP0xKmvHYl32jvst2BU4PgtY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qtrniovpkrwimeohamkc.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF0cm5pb3Zwa3J3aW1lb2hhbWtjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwMTY4NjUsImV4cCI6MjA5NjU5Mjg2NX0.j4gUqZlqMHR0ltIMCDB-UfWPvuPVs9B9HF0If2fPxhU")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "-1003823489442"))
SUPPORT_GROUP_ID = -1003823489442
PARTNERSHIP_GROUP_ID = -5467968653
SIRLY_STAFF_GROUP_ID = -5076135815
BUXGALTERIYA_PROMOKOD_GROUP_ID = -5574268734
MINIAPP_URL = os.environ.get("MINIAPP_URL", "https://pulatovumid102-tech.github.io/Grafik/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "20"))
MUAMMOLI_MUDDAT_SOAT = 24
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
KAITEN_DEPTS = [
    "Sotuv bo'limi",
    "Partnership bo'limi",
    "Support bo'limi",
    "IT bo'limi",
    "Buxgalteriya bo'limi",
    "Yuridik bo'limi",
]

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


async def sb_upsert(table: str, row_id: str, data: dict) -> None:
    """PATCH bilan bir xil, lekin qator hali mavjud bo'lmasa ham ishlaydi
    (mavjud bo'lsa yangilaydi, bo'lmasa yaratadi) — biznes_data uchun."""
    resp = await http_client.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=id",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json={"id": row_id, **data},
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
        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        usernames = collect_support_usernames(org_nodes)
        if usernames:
            text += "\n\n" + " ".join(f"@{u}" for u in usernames)
    except Exception as e:
        log.error("Support tag xatosi: %s", e)
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
def parse_tg_field(node: dict) -> list:
    """Xodim tugunida bir nechta username 'tgs' massivida saqlanadi;
    eski yozuvlarda faqat bitta 'tg' maydoni bo'lishi mumkin."""
    tgs = node.get("tgs")
    if isinstance(tgs, list) and tgs:
        return [str(t).strip().lstrip("@") for t in tgs if str(t).strip().lstrip("@")]
    tg = (node.get("tg") or "").strip()
    return [tg.lstrip("@")] if tg else []


def collect_dept_usernames(org_nodes: list, keyword: str) -> list:
    """Org struktura ичida nomi 'keyword' so'zini o'z ichiga olgan tugunni topib,
    uning barcha farzand tugunlaridan (bo'sh bo'lmagan tg maydoni bilan)
    Telegram username'larini yig'ib qaytaradi."""
    if not isinstance(org_nodes, list):
        return []
    dept_ids = [
        n.get("id") for n in org_nodes
        if keyword.lower() in (n.get("name") or "").lower()
    ]
    if not dept_ids:
        return []
    by_parent = {}
    for n in org_nodes:
        by_parent.setdefault(n.get("parentId"), []).append(n)

    usernames = []
    def walk(node_id):
        for child in by_parent.get(node_id, []):
            usernames.extend(parse_tg_field(child))
            walk(child.get("id"))

    for did in dept_ids:
        walk(did)
    return list(dict.fromkeys(usernames))


def collect_support_usernames(org_nodes: list) -> list:
    return collect_dept_usernames(org_nodes, "support")


def collect_all_usernames(org_nodes: list) -> list:
    """Org strukturadagi barcha xodimlardan (bo'sh bo'lmagan tg maydoni bilan)
    Telegram username'larini yig'ib qaytaradi."""
    if not isinstance(org_nodes, list):
        return []
    usernames = []
    for n in org_nodes:
        usernames.extend(parse_tg_field(n))
    return list(dict.fromkeys(usernames))


def norm_fio(s: str) -> str:
    """Ism-familiyani solishtirish uchun soddalashtiradi (apostrof/probel farqlarini olib tashlaydi)."""
    s = str(s or "").lower()
    for ch in ("'", "’", "ʻ", "`"):
        s = s.replace(ch, "")
    return " ".join(s.split())


def build_fio_tg_map(org_nodes: list) -> dict:
    """FIO (normallashtirilgan) -> Telegram username xaritasini quradi."""
    mapping = {}
    if not isinstance(org_nodes, list):
        return mapping
    for n in org_nodes:
        fio = (n.get("fio") or "").strip()
        if not fio:
            continue
        tgs = parse_tg_field(n)
        if tgs:
            mapping[norm_fio(fio)] = tgs[0]
    return mapping


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
            lines.append(f"⚠️ Hozircha muammoli mijozlarda {len(open_items)} ta ochiq murojaat bor")

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

        org_nodes = []
        try:
            org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
            org_nodes = org_rows[0]["data"] if org_rows else []
        except Exception as e:
            log.error("Org struktura tekshirish xatosi (overdue): %s", e)

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
                usernames = collect_support_usernames(org_nodes)
                tags = " ".join(f"@{u}" for u in usernames)
                text += "\n\n@umidpulatov"
                if tags:
                    text += " " + tags
                await app.bot.send_message(chat_id=SUPPORT_GROUP_ID, text=text)
                it["overdueNotified"] = True
                changed = True
        if changed:
            await sb_patch("biznes_data", "muammoli_mijozlar", {"data": muammoli_data})
            log.info("Muddati o'tgan murojaat(lar) uchun ogohlantirish yuborildi")
    except Exception as e:
        log.error("Muddat tekshirish xatosi: %s", e)


SCREENSHOT_STATE = {"count": 0, "confirmed": False}


def generate_screenshot_times() -> list:
    """10:30 dan 23:30 gacha, har 30 daqiqada."""
    times = []
    start_minutes = 10 * 60 + 30
    end_minutes = 23 * 60 + 30
    cur = start_minutes
    while cur <= end_minutes:
        h, m = divmod(cur, 60)
        times.append(dt_time(hour=h, minute=m, tzinfo=TASHKENT_TZ))
        cur += 30
    return times


async def screenshot_request_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    try:
        SCREENSHOT_STATE["count"] = 0
        SCREENSHOT_STATE["confirmed"] = False
        text = "📸 Iltimos, skrinshot yuboring"
        try:
            org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
            org_nodes = org_rows[0]["data"] if org_rows else []
            usernames = collect_support_usernames(org_nodes)
            if usernames:
                text += "\n\n" + " ".join(f"@{u}" for u in usernames)
        except Exception as e:
            log.error("Skrinshot so'rovida tag xatosi: %s", e)
        await app.bot.send_message(chat_id=SUPPORT_GROUP_ID, text=text)
        log.info("Skrinshot so'rovi yuborildi")
        context.job_queue.run_once(screenshot_followup_check, when=15 * 60)
    except Exception as e:
        log.error("Skrinshot so'rovi xatosi: %s", e)


async def screenshot_followup_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    try:
        if not SCREENSHOT_STATE["confirmed"]:
            await app.bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                text="⚠️ Support bo'limi xodimlari rasm yubormadi\n@umidpulatov",
            )
            log.info("Skrinshot kelmagani haqida ogohlantirish yuborildi")
    except Exception as e:
        log.error("Skrinshot follow-up xatosi: %s", e)


async def handle_support_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or update.effective_chat.id != SUPPORT_GROUP_ID:
        return
    user = update.effective_user
    if not user or not user.username:
        return
    if SCREENSHOT_STATE["confirmed"]:
        return
    try:
        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        usernames = collect_support_usernames(org_nodes)
    except Exception as e:
        log.error("Org struktura tekshirish xatosi: %s", e)
        return
    if user.username.lstrip("@") not in usernames:
        return

    SCREENSHOT_STATE["count"] += 1
    if SCREENSHOT_STATE["count"] >= 2:
        SCREENSHOT_STATE["confirmed"] = True
        try:
            await update.message.reply_text("✅ Rasmlar qabul qilindi")
        except Exception as e:
            log.error("Rasm tasdiqlash xatosi: %s", e)


async def check_serving_time_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """415 baza'dagi restoranlarning 'ovqat berish vaqti'gacha 1 soat qolganda
    Partnership guruhiga bir martalik eslatma yuboradi (kunlik, restoran uchun)."""
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.baza415"})
        if not rows:
            return
        baza_data = rows[0]["data"]
        if not isinstance(baza_data, dict):
            return
        restoranlar = baza_data.get("restoranlar", [])
        now = datetime.now(TASHKENT_TZ)
        today_str = now.strftime("%Y-%m-%d")
        matched = []
        changed = False
        for r in restoranlar:
            dan = r.get("berishVaqtiDan")
            if not dan:
                continue
            try:
                h, m = map(int, dan.split(":"))
            except Exception:
                continue
            serving_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            diff_minutes = (serving_dt - now).total_seconds() / 60
            if 89 <= diff_minutes <= 90 and r.get("oxirgiEslatmaSanasi") != today_str:
                matched.append(r)
                r["oxirgiEslatmaSanasi"] = today_str
                changed = True
        if matched:
            lines = [
                f"⏰ Berish vaqti boshlanishiga 1 soat 30 daqiqa qolgan {len(matched)} ta restoran bor",
                "Ularni Partnership bo'limidan kirib ko'ring",
                "",
            ]
            for r in matched:
                gacha = r.get("berishVaqtiGacha") or ""
                vaqt = r.get("berishVaqtiDan", "") + (("–" + gacha) if gacha else "")
                lines.append(f"🏪 {r.get('nom','—')} — {vaqt}")
            try:
                org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
                org_nodes = org_rows[0]["data"] if org_rows else []
                usernames = collect_dept_usernames(org_nodes, "partnership")
                if usernames:
                    lines.append("")
                    lines.append(" ".join(f"@{u}" for u in usernames))
            except Exception as e:
                log.error("Org struktura tag xatosi: %s", e)
            await app.bot.send_message(chat_id=PARTNERSHIP_GROUP_ID, text="\n".join(lines))
            log.info("Berish vaqti eslatmasi yuborildi: %d ta restoran", len(matched))
        if changed:
            await sb_patch("biznes_data", "baza415", {"data": baza_data})
    except Exception as e:
        log.error("Berish vaqti eslatmasi xatosi: %s", e)


async def check_calling_status_before_serving(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ovqat berish vaqtidan 2 daqiqa oldin, o'sha vaqtga to'g'ri kelgan
    restoranlar orasida kim tel qilingan, kim qilinmaganini Partnership
    guruhiga yuboradi."""
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.baza415"})
        if not rows:
            return
        baza_data = rows[0]["data"]
        if not isinstance(baza_data, dict):
            return
        restoranlar = baza_data.get("restoranlar", [])
        now = datetime.now(TASHKENT_TZ)
        today_str = now.strftime("%Y-%m-%d")
        changed = False

        # Vaqti 1-2 daqiqa qolgan (bugun hali yuborilmagan) guruhlarni topamiz
        due_times = set()
        for r in restoranlar:
            dan = r.get("berishVaqtiDan")
            if not dan:
                continue
            try:
                h, m = map(int, dan.split(":"))
            except Exception:
                continue
            serving_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            diff_minutes = (serving_dt - now).total_seconds() / 60
            if 1 <= diff_minutes <= 2 and r.get("holatXabarSanasi_" + dan) != today_str:
                due_times.add(dan)

        for dan in due_times:
            group = [r for r in restoranlar if r.get("berishVaqtiDan") == dan]
            called = [r for r in group if (r.get("qongiroq") or {}).get("lastCalledDate") == today_str]
            not_called = [r for r in group if (r.get("qongiroq") or {}).get("lastCalledDate") != today_str]

            lines = [f"📋 {dan} uchun qo'ng'iroqlar holati", ""]
            lines.append(f"✅ Tel qilingan: {len(called)} ta")
            for r in called:
                lines.append(f"🏪 {r.get('nom','—')}")
            lines.append("")
            lines.append(f"⏳ Tel qilinmagan: {len(not_called)} ta")
            for r in not_called:
                lines.append(f"🏪 {r.get('nom','—')}")

            await app.bot.send_message(chat_id=PARTNERSHIP_GROUP_ID, text="\n".join(lines))
            log.info("Qo'ng'iroq holati yuborildi: %s", dan)

            for r in group:
                r["holatXabarSanasi_" + dan] = today_str
            changed = True

        if changed:
            await sb_patch("biznes_data", "baza415", {"data": baza_data})
    except Exception as e:
        log.error("Qo'ng'iroq holati xatosi: %s", e)


async def daily_calling_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni 23:00 (Toshkent) da, 415 baza'dagi barcha restoranlar
    orasida bugun kim tel qilingan, kim qilinmaganini Partnership
    guruhiga umumiy hisobot sifatida yuboradi."""
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.baza415"})
        if not rows:
            return
        baza_data = rows[0]["data"]
        if not isinstance(baza_data, dict):
            return
        restoranlar = [r for r in baza_data.get("restoranlar", []) if r.get("berishVaqtiDan")]
        today = datetime.now(TASHKENT_TZ)
        today_str = today.strftime("%Y-%m-%d")
        today_display = today.strftime("%d.%m.%Y")

        called = [r for r in restoranlar if (r.get("qongiroq") or {}).get("lastCalledDate") == today_str]
        not_called = [r for r in restoranlar if (r.get("qongiroq") or {}).get("lastCalledDate") != today_str]

        lines = [f"📊 KUNLIK QO'NG'IROQLAR HISOBOTI — {today_display}", ""]
        lines.append(f"✅ Tel qilingan: {len(called)} ta")
        for r in called:
            lines.append(f"🏪 {r.get('nom','—')}")
        lines.append("")
        lines.append(f"❌ Tel qilinmagan: {len(not_called)} ta")
        for r in not_called:
            lines.append(f"🏪 {r.get('nom','—')}")

        await app.bot.send_message(chat_id=PARTNERSHIP_GROUP_ID, text="\n".join(lines))
        log.info("Kunlik qo'ng'iroqlar hisoboti yuborildi: %d/%d", len(called), len(restoranlar))
    except Exception as e:
        log.error("Kunlik qo'ng'iroqlar hisoboti xatosi: %s", e)


def _fmt_date_only(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")) if "T" in iso else datetime.fromisoformat(iso)
    except Exception:
        return iso
    return dt.astimezone(TASHKENT_TZ).strftime("%d.%m.%Y")


def _bux_signoff(ws, start_row: int, last_col: int) -> None:
    bold = Font(name="Arial", bold=True, size=11)
    normal = Font(name="Arial", size=10)
    rows = [
        ("Operatsion direktor:", "Umid Pulatov"),
        ("Buxgalter:", "Zilola Maxamatjonova"),
        ("Support bo'limi boshlig'i:", ""),
    ]
    for i, (label, name) in enumerate(rows):
        r = start_row + i
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        lbl_cell = ws.cell(row=r, column=1, value=label)
        lbl_cell.font = bold
        lbl_cell.alignment = Alignment(horizontal="left", vertical="center")

        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        val_cell = ws.cell(row=r, column=4, value=name if name else "_______________________")
        val_cell.font = normal
        val_cell.alignment = Alignment(horizontal="left", vertical="center")

        sign_col = max(7, last_col - 1)
        ws.cell(row=r, column=sign_col, value="Imzo:").font = bold
        ws.merge_cells(start_row=r, start_column=sign_col + 1, end_row=r, end_column=last_col)
        ws.cell(row=r, column=sign_col + 1, value="_______________")
        ws.row_dimensions[r].height = 20


def build_promokod_excel(items: list, today_display: str) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Promokod"

    normal = Font(name="Arial", size=10)
    header_font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1E7A4A")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    ws.merge_cells("A1:H1")
    ws["A1"] = f"Sana: {today_display}"
    ws["A1"].font = Font(name="Arial", bold=True, size=13)
    ws.row_dimensions[1].height = 22

    ws.merge_cells("A2:H2")
    ws["A2"] = "PROMOKOD BERISH KERAK — Haftalik hisobot"
    ws["A2"].font = Font(name="Arial", bold=True, size=12, color="1E7A4A")
    ws.row_dimensions[2].height = 20

    headers = ["№", "Murojaat sanasi", "Mijoz", "Mijoz raqami", "Restoran", "Sabab", "Support bo'limi xodimi", "Karta raqami"]
    header_row = 4
    ws.row_dimensions[header_row].height = 34
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    for idx, it in enumerate(items, start=1):
        r = header_row + idx
        ws.row_dimensions[r].height = 45
        row_vals = [
            idx,
            _fmt_date_only(it.get("createdAt", "")),
            it.get("ism") or "—",
            it.get("tel") or "—",
            it.get("restoran") or "—",
            it.get("turi") or "—",
            it.get("createdByName") or "—",
            it.get("promokodKartaRaqami") or "—",
        ]
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = normal
            cell.border = border
            cell.alignment = center if c_idx in (1, 2, 3) else left

    sign_start = header_row + len(items) + 3
    _bux_signoff(ws, sign_start, 8)

    widths = [5, 14, 14, 15, 16, 36, 20, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def build_pul_berish_excel(items: list, today_display: str) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Pul berish"

    normal = Font(name="Arial", size=10)
    bold = Font(name="Arial", bold=True, size=11)
    header_font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="E34948")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    ws.merge_cells("A1:J1")
    ws["A1"] = f"Sana: {today_display}"
    ws["A1"].font = Font(name="Arial", bold=True, size=13)
    ws.row_dimensions[1].height = 22

    ws.merge_cells("A2:J2")
    ws["A2"] = "RESTORANGA PUL TASHLAB BERISH KERAK — Haftalik hisobot"
    ws["A2"].font = Font(name="Arial", bold=True, size=12, color="B0202A")
    ws.row_dimensions[2].height = 20

    headers = ["№", "Murojaat sanasi", "Mijoz", "Mijoz raqami", "Restoran", "Sabab", "Support bo'limi xodimi", "Box soni", "Box narxi", "Jami summa"]
    header_row = 4
    ws.row_dimensions[header_row].height = 34
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    for idx, it in enumerate(items, start=1):
        r = header_row + idx
        ws.row_dimensions[r].height = 45
        soni = it.get("boxSoni") or 1
        narx = it.get("boxSummasi") or 20000
        row_vals = [
            idx,
            _fmt_date_only(it.get("createdAt", "")),
            it.get("ism") or "—",
            it.get("tel") or "—",
            it.get("restoran") or "—",
            it.get("turi") or "—",
            it.get("createdByName") or "—",
            soni,
            narx,
            soni * narx,
        ]
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=c_idx, value=val)
            cell.font = normal
            cell.border = border
            cell.alignment = center if c_idx in (1, 2, 3, 8, 9, 10) else left
            if c_idx in (9, 10):
                cell.number_format = '#,##0 "so\'m"'

    total_row = header_row + len(items) + 1
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=9)
    tot_lbl = ws.cell(row=total_row, column=1, value="JAMI TO'LANADIGAN SUMMA:")
    tot_lbl.font = bold
    tot_lbl.alignment = Alignment(horizontal="right", vertical="center")
    tot_val = ws.cell(row=total_row, column=10, value=f"=SUM(J{header_row+1}:J{header_row+len(items)})" if items else 0)
    tot_val.font = Font(name="Arial", bold=True, size=11, color="B0202A")
    tot_val.number_format = '#,##0 "so\'m"'
    tot_val.border = border

    sign_start = total_row + 3
    _bux_signoff(ws, sign_start, 10)

    widths = [5, 14, 13, 15, 16, 36, 20, 10, 12, 13]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def weekly_buxgalteriya_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har juma 10:00 (Toshkent) da, hal bo'lmagan murojaatlar orasida
    'Promokod berish kerak' va 'Restoranga pul tashlab berish kerak'
    deb belgilanganlarning Excel fayllarini Buxgalteriya guruhiga yuboradi."""
    app = context.application
    try:
        rows = await sb_get("biznes_data", params={"id": "eq.muammoli_mijozlar"})
        muammoli_data = rows[0]["data"] if rows else {}
        items = muammoli_data.get("items", []) if isinstance(muammoli_data, dict) else []
        open_items = [it for it in items if not it.get("archived") and it.get("holati") != "hal_qilindi"]

        promokod_items = [it for it in open_items if it.get("promokodKerak")]
        pul_items = [it for it in open_items if it.get("tasdiqlamadiLekinBekor")]

        today_display = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y")
        date_tag = datetime.now(TASHKENT_TZ).strftime("%Y%m%d")

        text = (
            "📋 Promokod va restoran tasdiqlamagan sifatsiz taom uchun to'lov "
            "ro'yxati quyidagi Excel fayllarda"
        )
        await app.bot.send_message(chat_id=BUXGALTERIYA_PROMOKOD_GROUP_ID, text=text)

        promokod_buf = build_promokod_excel(promokod_items, today_display)
        await app.bot.send_document(
            chat_id=BUXGALTERIYA_PROMOKOD_GROUP_ID,
            document=promokod_buf,
            filename=f"promokod_{date_tag}.xlsx",
        )

        pul_buf = build_pul_berish_excel(pul_items, today_display)
        await app.bot.send_document(
            chat_id=BUXGALTERIYA_PROMOKOD_GROUP_ID,
            document=pul_buf,
            filename=f"restoranga_pul_berish_{date_tag}.xlsx",
        )

        log.info("Haftalik buxgalteriya hisoboti yuborildi: %d promokod, %d pul", len(promokod_items), len(pul_items))
    except Exception as e:
        log.error("Haftalik buxgalteriya hisoboti xatosi: %s", e)


# ============================================================
# ISH DAVOMATI — krujok (video note) orqali tasdiqlash
# ============================================================
ATTENDANCE_STATE_ID = "ish_davomat"


def _org_employees_with_schedule(org_nodes: list) -> list:
    """ishBoshlanish maydoni to'ldirilgan barcha xodimlarni qaytaradi."""
    if not isinstance(org_nodes, list):
        return []
    return [n for n in org_nodes if n.get("ishBoshlanish")]


def _today_ish_kun_key() -> str:
    kunlar = ["dush", "sesh", "chor", "pay", "juma", "shan", "yak"]
    return kunlar[datetime.now(TASHKENT_TZ).weekday()]


async def check_ish_boshlanish_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har xodimning ish boshlanish vaqtiga 10 daqiqa qolganda, Sirly Staff
    guruhiga o'sha vaqtga to'g'ri keladigan xodimlarni tag qilib eslatma yuboradi."""
    app = context.application
    try:
        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        employees = _org_employees_with_schedule(org_nodes)
        if not employees:
            return

        today_kun = _today_ish_kun_key()
        now = datetime.now(TASHKENT_TZ)
        today_str = now.strftime("%Y-%m-%d")

        state_rows = await sb_get("biznes_data", params={"id": f"eq.{ATTENDANCE_STATE_ID}"})
        state = state_rows[0]["data"] if state_rows and isinstance(state_rows[0].get("data"), dict) else {}
        reminded = state.setdefault("reminded", {}).setdefault(today_str, [])

        due_times = set()
        for n in employees:
            kunlar = n.get("ishKunlari")
            if kunlar is not None and today_kun not in kunlar:
                continue
            vaqt = n.get("ishBoshlanish")
            try:
                h, m = map(int, vaqt.split(":"))
            except Exception:
                continue
            start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            diff_minutes = (start_dt - now).total_seconds() / 60
            key = vaqt
            if 9 <= diff_minutes <= 10 and key not in reminded:
                due_times.add(vaqt)

        if not due_times:
            return

        for vaqt in due_times:
            group = [
                n for n in employees
                if n.get("ishBoshlanish") == vaqt
                and (n.get("ishKunlari") is None or today_kun in n.get("ishKunlari"))
            ]
            if not group:
                continue
            usernames = []
            for n in group:
                tgs = parse_tg_field(n)
                if tgs:
                    usernames.append(tgs[0])
            tag_line = " ".join(f"@{u}" for u in usernames) if usernames else ""
            text = f"⏰ Ish vaqti boshlanishiga 10 daqiqa qolgan xodimlar ({vaqt}):\n{tag_line}"
            await app.bot.send_message(chat_id=SIRLY_STAFF_GROUP_ID, text=text)
            reminded.append(vaqt)
            log.info("Ish boshlanish eslatmasi yuborildi: %s (%d xodim)", vaqt, len(group))

        await sb_upsert("biznes_data", ATTENDANCE_STATE_ID, {"data": state})
    except Exception as e:
        log.error("Ish boshlanish eslatmasi xatosi: %s", e)


async def handle_staff_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sirly Staff guruhiga kelgan krujok (video note) xabarlarini kuzatib,
    yuboruvchini ishga kelgan deb belgilaydi."""
    if not update.effective_chat or update.effective_chat.id != SIRLY_STAFF_GROUP_ID:
        return
    user = update.effective_user
    if not user or not user.username:
        return
    try:
        now = datetime.now(TASHKENT_TZ)
        today_str = now.strftime("%Y-%m-%d")
        username = user.username.lstrip("@")

        state_rows = await sb_get("biznes_data", params={"id": f"eq.{ATTENDANCE_STATE_ID}"})
        state = state_rows[0]["data"] if state_rows and isinstance(state_rows[0].get("data"), dict) else {}
        kelganlar = state.setdefault("kelganlar", {}).setdefault(today_str, {})
        if username in kelganlar:
            return  # allaqachon tasdiqlangan
        kelganlar[username] = now.strftime("%H:%M:%S")

        await sb_upsert("biznes_data", ATTENDANCE_STATE_ID, {"data": state})
        try:
            await update.message.reply_text(f"✅ {now.strftime('%H:%M')} da ishga kelganingiz qayd etildi")
        except Exception:
            pass
        log.info("Davomat qayd etildi: %s -> %s", username, now.strftime("%H:%M:%S"))
    except Exception as e:
        log.error("Davomat qayd etish xatosi: %s", e)


async def check_ish_kelmagan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har xodimning ish boshlanishidan 30 daqiqa o'tgach, agar krujok
    kelmagan bo'lsa, Sirly Staff guruhiga kelmaganlar ro'yxatini yuboradi."""
    app = context.application
    try:
        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        employees = _org_employees_with_schedule(org_nodes)
        if not employees:
            return

        today_kun = _today_ish_kun_key()
        now = datetime.now(TASHKENT_TZ)
        today_str = now.strftime("%Y-%m-%d")

        state_rows = await sb_get("biznes_data", params={"id": f"eq.{ATTENDANCE_STATE_ID}"})
        state = state_rows[0]["data"] if state_rows and isinstance(state_rows[0].get("data"), dict) else {}
        kelganlar = state.get("kelganlar", {}).get(today_str, {})
        checked = state.setdefault("kelmagan_tekshirildi", {}).setdefault(today_str, [])

        due_times = set()
        for n in employees:
            kunlar = n.get("ishKunlari")
            if kunlar is not None and today_kun not in kunlar:
                continue
            vaqt = n.get("ishBoshlanish")
            try:
                h, m = map(int, vaqt.split(":"))
            except Exception:
                continue
            start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            diff_minutes = (now - start_dt).total_seconds() / 60
            if 29 <= diff_minutes <= 30 and vaqt not in checked:
                due_times.add(vaqt)

        if not due_times:
            return

        for vaqt in due_times:
            group = [
                n for n in employees
                if n.get("ishBoshlanish") == vaqt
                and (n.get("ishKunlari") is None or today_kun in n.get("ishKunlari"))
            ]
            missing = []
            for n in group:
                tgs = parse_tg_field(n)
                username = tgs[0] if tgs else None
                if not username or username not in kelganlar:
                    missing.append(n.get("fio") or n.get("name") or "—")
            checked.append(vaqt)
            if missing:
                lines = [f"❌ Ishga kelmadi ({vaqt} boshlanishi kerak edi, 30 daqiqa o'tdi):"]
                for fio in missing:
                    lines.append(f"👤 {fio}")
                lines.append("")
                lines.append("@umidpulatov")
                await app.bot.send_message(chat_id=SIRLY_STAFF_GROUP_ID, text="\n".join(lines))
                log.info("Kelmaganlar ro'yxati yuborildi: %s (%d kishi)", vaqt, len(missing))

        await sb_upsert("biznes_data", ATTENDANCE_STATE_ID, {"data": state})
    except Exception as e:
        log.error("Kelmaganlar tekshiruvi xatosi: %s", e)


# ============================================================
# KAITEN — ERTANGI DEDLAYNLAR HAQIDA KUNLIK ESLATMA (23:00)
# ============================================================
def _kaiten_fmt_deadline(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")) if "T" in iso else datetime.fromisoformat(iso)
    except Exception:
        return iso
    return dt.strftime("%d.%m.%Y %H:%M")


async def _kaiten_deadline_digest(context: ContextTypes.DEFAULT_TYPE, days_ahead: int, title: str) -> None:
    """Kaiten vazifalarini (bugun yoki ertaga muddati tugaydiganlarni)
    bo'limlar bo'yicha guruhlab, Sirly xodimlar guruhiga yuboradi.
    Ijrochi va nazoratchi @username orqali taglanadi."""
    app = context.application
    try:
        kaiten_rows = await sb_get("biznes_data", params={"id": "eq.kaiten"})
        kaiten_data = kaiten_rows[0]["data"] if kaiten_rows else {}
        tasks = kaiten_data.get("tasks", []) if isinstance(kaiten_data, dict) else []

        org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
        org_nodes = org_rows[0]["data"] if org_rows else []
        fio_tg_map = build_fio_tg_map(org_nodes)

        target_day = datetime.now(TASHKENT_TZ) + timedelta(days=days_ahead)
        target_str = target_day.strftime("%Y-%m-%d")
        target_display = target_day.strftime("%d.%m.%Y")

        filtered = [
            t for t in tasks
            if not t.get("archived")
            and t.get("status") in ("todo", "progress")
            and t.get("deadline")
            and str(t["deadline"]).split("T")[0] == target_str
        ]

        divider = "━━━━━━━━━━━━━"
        lines = [divider, f"{title} — {target_display}", divider]

        if not filtered:
            lines.append("")
            lines.append(f"✅ ({target_display}) muddati tugaydigan vazifalar yo'q.")
        else:
            by_dept = {}
            for t in filtered:
                dept = t.get("dept") or "Boshqa"
                by_dept.setdefault(dept, []).append(t)

            dept_order = list(KAITEN_DEPTS) + [d for d in by_dept if d not in KAITEN_DEPTS]

            for dept in dept_order:
                dept_tasks = by_dept.get(dept)
                if not dept_tasks:
                    continue
                lines.append("")
                lines.append(f"🏢 {dept}")
                for t in dept_tasks:
                    emp_fio = t.get("empFio") or "—"
                    emp_tg = fio_tg_map.get(norm_fio(emp_fio), "") or (t.get("empTg") or "").strip().lstrip("@")
                    ijrochi_line = emp_fio + (f" @{emp_tg}" if emp_tg else "")

                    naz_fio = t.get("nazFio")
                    if naz_fio:
                        naz_tg = fio_tg_map.get(norm_fio(naz_fio), "")
                        nazoratchi_line = naz_fio + (f" @{naz_tg}" if naz_tg else "")
                    else:
                        nazoratchi_line = "— (belgilanmagan)"

                    lines.append("")
                    lines.append(f'📌 "{t.get("text","")}"')
                    lines.append(f"🙋 Ijrochi: {ijrochi_line}")
                    lines.append(f"👁 Nazoratchi: {nazoratchi_line}")
                    lines.append(f"⏰ Muddat: {_kaiten_fmt_deadline(t.get('deadline',''))}")
                lines.append(divider)

            lines.append(f"Jami: {len(filtered)} ta vazifa muddati ({target_display}) tugaydi.")

        await app.bot.send_message(chat_id=SIRLY_STAFF_GROUP_ID, text="\n".join(lines))
        log.info("%s yuborildi: %d ta vazifa", title, len(filtered))
    except Exception as e:
        log.error("Kaiten dedlayn digest xatosi (%s): %s", title, e)


async def daily_deadline_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni 23:00 (Toshkent) da ertangi kunga muddati tugaydigan vazifalar."""
    await _kaiten_deadline_digest(context, days_ahead=1, title="⏰ ERTANGI DEDLAYNLAR")


async def daily_today_tasks_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni 10:00 (Toshkent) da bugun tugaydigan vazifalar ro'yxati."""
    await _kaiten_deadline_digest(context, days_ahead=0, title="📋 BUGUNGI ISHLAR RO'YXATI")


async def check_deadline_2h_before(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Vazifa dedlayniga 2 soat qolganda, Sirly Staff guruhiga bir martalik
    eslatma yuboradi (ijrochi va nazoratchi taglanadi)."""
    app = context.application
    try:
        kaiten_rows = await sb_get("biznes_data", params={"id": "eq.kaiten"})
        if not kaiten_rows:
            return
        kaiten_data = kaiten_rows[0]["data"]
        if not isinstance(kaiten_data, dict):
            return
        tasks = kaiten_data.get("tasks", [])

        now = datetime.now(TASHKENT_TZ)
        due = []
        changed = False
        for t in tasks:
            if t.get("archived") or t.get("status") not in ("todo", "progress"):
                continue
            if t.get("deadline2hNotified"):
                continue
            deadline = t.get("deadline")
            if not deadline:
                continue
            try:
                dl = datetime.fromisoformat(deadline)
                if dl.tzinfo is None:
                    dl = dl.replace(tzinfo=TASHKENT_TZ)
            except Exception:
                continue
            diff_minutes = (dl - now).total_seconds() / 60
            if 119 <= diff_minutes <= 121:
                due.append(t)
                t["deadline2hNotified"] = True
                changed = True

        if due:
            org_rows = await sb_get("biznes_data", params={"id": "eq.org"})
            org_nodes = org_rows[0]["data"] if org_rows else []
            fio_tg_map = build_fio_tg_map(org_nodes)

            divider = "━━━━━━━━━━━━━"
            for t in due:
                emp_fio = t.get("empFio") or "—"
                emp_tg = fio_tg_map.get(norm_fio(emp_fio), "") or (t.get("empTg") or "").strip().lstrip("@")
                ijrochi_line = emp_fio + (f" @{emp_tg}" if emp_tg else "")

                naz_fio = t.get("nazFio")
                if naz_fio:
                    naz_tg = fio_tg_map.get(norm_fio(naz_fio), "")
                    nazoratchi_line = naz_fio + (f" @{naz_tg}" if naz_tg else "")
                else:
                    nazoratchi_line = "— (belgilanmagan)"

                lines = [
                    divider,
                    "⏳ DEDLAYNGACHA 2 SOAT QOLDI",
                    divider,
                    "",
                    f'📌 "{t.get("text","")}"',
                    f"🏢 {t.get('dept','—')}",
                    f"🙋 Ijrochi: {ijrochi_line}",
                    f"👁 Nazoratchi: {nazoratchi_line}",
                    f"⏰ Muddat: {_kaiten_fmt_deadline(t.get('deadline',''))}",
                    divider,
                ]
                await app.bot.send_message(chat_id=SIRLY_STAFF_GROUP_ID, text="\n".join(lines))
            log.info("2 soatlik dedlayn eslatmasi yuborildi: %d ta vazifa", len(due))

        if changed:
            await sb_patch("biznes_data", "kaiten", {"data": kaiten_data})
    except Exception as e:
        log.error("2 soatlik dedlayn eslatmasi xatosi: %s", e)


# ============================================================
# DAVRIY TEKSHIRUV (JobQueue)
# ============================================================
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    await process_group_messages(app)
    await process_reminders(app)
    await process_file_requests(app)


# ============================================================
# /test_dedlayn BUYRUG'I — 23:00 ni kutmasdan, xabarni darhol
# yuborib ko'rish uchun (test maqsadida)
# ============================================================
async def test_deadline_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Tekshirilmoqda, biroz kuting...")
    await daily_deadline_reminder(context)
    await update.message.reply_text(
        "✅ Tayyor! Sirly xodimlar guruhini tekshiring — xabar o'sha yerga yuborildi."
    )


# ============================================================
# /test_hisobot BUYRUG'I — juma 10:00 ni kutmasdan, Buxgalteriya
# hisobotini (matn + Excel fayllar) darhol yuborib ko'rish uchun
# ============================================================
async def test_hisobot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Tekshirilmoqda, biroz kuting...")
    await weekly_buxgalteriya_report(context)
    await update.message.reply_text(
        "✅ Tayyor! Buxgalteriya guruhini tekshiring — matn va Excel fayllar o'sha yerga yuborildi."
    )


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
    app.add_handler(CommandHandler("test_dedlayn", test_deadline_cmd))
    app.add_handler(CommandHandler("test_hisobot", test_hisobot_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_support_photo))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_staff_video_note))
    app.job_queue.run_repeating(poll_job, interval=POLL_SECONDS, first=5)

    # Skrinshot so'rovi — har 30 daqiqada, 10:30 dan 23:30 gacha
    for shot_time in generate_screenshot_times():
        app.job_queue.run_daily(screenshot_request_job, time=shot_time)

    # Muammoli mijozlar — davriy TEKSHIRUV xabari O'CHIRILGAN (foydalanuvchi so'rovi bo'yicha)
    # for check_time in generate_check_times():
    #     app.job_queue.run_daily(muammoli_check_job, time=check_time)

    # Muammoli mijozlar — kunlik eslatma, har kuni 10:30, 15:00, 19:00 (Toshkent vaqti)
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=10, minute=30, tzinfo=TASHKENT_TZ))
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=15, minute=0, tzinfo=TASHKENT_TZ))
    app.job_queue.run_daily(daily_muammoli_reminder, time=dt_time(hour=19, minute=0, tzinfo=TASHKENT_TZ))

    # Muammoli mijozlar — 24 soatlik muddat nazorati, har 30 daqiqada tekshiriladi
    app.job_queue.run_repeating(check_overdue_muammoli, interval=1800, first=60)

    # 415 baza — ovqat berish vaqtiga 1 soat qolganda Partnership guruhiga eslatma
    app.job_queue.run_repeating(check_serving_time_reminders, interval=60, first=30)
    app.job_queue.run_repeating(check_calling_status_before_serving, interval=60, first=45)

    # Kaiten — ertangi dedlaynlar haqida kunlik eslatma, har kuni 23:00 (Toshkent vaqti)
    app.job_queue.run_daily(daily_deadline_reminder, time=dt_time(hour=23, minute=0, tzinfo=TASHKENT_TZ))

    # Kaiten — bugungi ishlar ro'yxati, har kuni 10:00 (Toshkent vaqti)
    app.job_queue.run_daily(daily_today_tasks_reminder, time=dt_time(hour=10, minute=0, tzinfo=TASHKENT_TZ))

    # Buxgalteriya — haftalik hisobot (Promokod + Pul berish), faqat JUMA 10:00 (Toshkent vaqti)
    app.job_queue.run_daily(weekly_buxgalteriya_report, time=dt_time(hour=10, minute=0, tzinfo=TASHKENT_TZ), days=(4,))

    # Ish davomati — ish boshlanishiga 10 daqiqa qolganda eslatma, har daqiqada tekshiriladi
    app.job_queue.run_repeating(check_ish_boshlanish_reminder, interval=60, first=15)
    # Ish davomati — ish boshlanishidan 30 daqiqa o'tsa, kelmaganlar ro'yxati
    app.job_queue.run_repeating(check_ish_kelmagan, interval=60, first=20)

    # Partnership — kunlik qo'ng'iroqlar hisoboti, har kuni 23:00 (Toshkent vaqti)
    app.job_queue.run_daily(daily_calling_report, time=dt_time(hour=23, minute=0, tzinfo=TASHKENT_TZ))

    # Kaiten — dedlaynga 2 soat qolganda eslatma, har daqiqada tekshiriladi
    app.job_queue.run_repeating(check_deadline_2h_before, interval=60, first=50)

    log.info("Bot polling boshlandi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
