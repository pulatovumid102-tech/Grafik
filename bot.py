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
from datetime import datetime, timezone

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# SOZLAMALAR — to'g'ridan-to'g'ri shu yerga yozilgan
# (Railway'da Variables qo'shish shart emas, lekin xohlasangiz
#  pastdagi os.environ.get(...) orqali Variables bilan ustidan
#  yozib qo'yish ham mumkin — hozircha shart emas)
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8693834890:AAHgdy4LkMH6zVgnky2rFVoeoxCpmzsRdMM")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qtrniovpkrwimeohamkc.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF0cm5pb3Zwa3J3aW1lb2hhbWtjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwMTY4NjUsImV4cCI6MjA5NjU5Mjg2NX0.j4gUqZlqMHR0ltIMCDB-UfWPvuPVs9B9HF0If2fPxhU")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "-5531952742"))
MINIAPP_URL = os.environ.get("MINIAPP_URL", "https://pulatovumid102-tech.github.io/Grafik/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "20"))

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
            await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
            await sb_patch("bot_group_messages", row_id, {"status": "sent"})
            log.info("Guruhga yuborildi: %s", row_id)
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
    app.job_queue.run_repeating(poll_job, interval=POLL_SECONDS, first=5)

    log.info("Bot polling boshlandi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
