import logging
import calendar
import os
import threading
import http.server
import pytz
from datetime import datetime, timezone, time as dt_time, date as dt_date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
import httpx

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Sozlamalar =====
TOKEN = "8500527121:AAF_Z3rqt9ZxbrygkI_DQMgitoO3WzTj5Ss"
CHAT_ID = -1003914304171
CHANNEL_IDS = [-1004451061109, -1001644206432]

SB_URL = "https://ubakgpkcemlchpfejmke.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU"
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Mini App manzili
WEBAPP_URL = "https://pulatovumid102-tech.github.io/Sirly-assistant/"
BOT_USERNAME = "atigabirbet_bot"


SUBSCRIPTION_PRICE = 250  # Stars
ADMIN_ID_BOT = 1645167548


# ===== Buyruqlar =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    # /start subscribe dan kelgan bo'lsa — invoice yuborish
    if args and args[0] == 'subscribe':
        await subscribe_command(update, context)
        return
    await update.message.reply_text(
        "Salom! \"Neyra\" ilovasiga xush kelibsiz 📖\n\n"
        "Ilovani ochish uchun Menu tugmasini bosing."
    )
    # Foydalanuvchi rasmini olish va saqlash
    try:
        user = update.effective_user
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        photo_url = None
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            photo_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{SB_URL}/rest/v1/user_profiles",
                headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
                json={"user_id": user.id, "user_name": user.full_name, "photo_url": photo_url}
            )
    except Exception as e:
        logger.error(f"start rasm saqlash xato: {e}")


# ===== Obuna tizimi =====
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_invoice(
        chat_id=user.id,
        title="Neyra — Oylik obuna",
        description="Neyra ilovasiga 30 kunlik kirish huquqi",
        payload=f"sub_{user.id}",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Oylik obuna", "amount": SUBSCRIPTION_PRICE}],
    )


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    user = update.effective_user
    payment = update.message.successful_payment
    try:
        expires = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{SB_URL}/rest/v1/subscriptions",
                headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
                json={"user_id": user.id, "user_name": user.full_name, "status": "active",
                      "expires_at": expires, "stars_paid": payment.total_amount,
                      "updated_at": datetime.datetime.utcnow().isoformat()}
            )
        await update.message.reply_text(
            f"✅ To'lov qabul qilindi!\n💫 {payment.total_amount} Stars\n📅 {expires} gacha\n\nNeyra ga xush kelibsiz! 🌱"
        )
    except Exception as e:
        logger.error(f"To'lov xato: {e}")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    if update.effective_user.id != ADMIN_ID_BOT:
        return
    today = datetime.date.today().isoformat()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{SB_URL}/rest/v1/subscriptions?select=*&order=created_at.desc", headers=SB_HEADERS)
            subs = r.json()
        active, trial, expired = [], [], []
        for s in subs:
            name = s.get('user_name', str(s['user_id']))
            uid = s['user_id']
            if s['status'] == 'active' and s.get('expires_at', '') >= today:
                active.append(f"✅ {name} · {s.get('expires_at','')}")
            elif s['status'] == 'trial' and s.get('trial_end', '') >= today:
                trial.append(f"🟡 {name} · {s.get('trial_end','')}")
            else:
                expired.append(f"❌ {name} (uid:{uid})")
        msg = "📊 Neyra foydalanuvchilari:\n\n"
        if active: msg += "✅ Faol:\n" + "\n".join(active) + "\n\n"
        if trial: msg += "🟡 Sinov:\n" + "\n".join(trial) + "\n\n"
        if expired: msg += "❌ To'lamagan:\n" + "\n".join(expired) + "\n\n"
        msg += f"Jami: {len(subs)} ta"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")


# ===== Kontakt so'rovlarini tekshirish (fon vazifasi) =====
async def check_contact_requests(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"status": "eq.pending", "select": "*"},
            )
            rows = r.json()
            for row in rows:
                try:
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Ha", callback_data=f"cr_yes_{row['id']}"),
                        InlineKeyboardButton("❌ Yo'q", callback_data=f"cr_no_{row['id']}"),
                    ]])
                    await context.bot.send_message(
                        chat_id=row["target_id"],
                        text=(
                            f"👤 {row['requester_name']} siz bilan bog'lanishni so'rayapti.\n\n"
                            "Profilingizni unga ulashishga roziman?"
                        ),
                        reply_markup=kb,
                    )
                    await client.patch(
                        f"{SB_URL}/rest/v1/contact_requests",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['id']}"},
                        json={"status": "sent"},
                    )
                except Exception as e:
                    logger.error(f"Kontakt so'rovi yuborilmadi (id={row.get('id')}): {e}")
                    await client.patch(
                        f"{SB_URL}/rest/v1/contact_requests",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['id']}"},
                        json={"status": "failed"},
                    )
    except Exception as e:
        logger.error(f"check_contact_requests xato: {e}")


async def contact_response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) != 3:
        return
    _, action, req_id = parts
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{SB_URL}/rest/v1/contact_requests",
            headers=SB_HEADERS,
            params={"id": f"eq.{req_id}", "select": "*"},
        )
        rows = r.json()
        if not rows:
            return
        row = rows[0]
        now_iso = datetime.now(timezone.utc).isoformat()
        if action == "yes":
            await client.patch(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"id": f"eq.{req_id}"},
                json={"status": "agreed", "responded_at": now_iso},
            )
            username = query.from_user.username
            contact_line = f"@{username}" if username else f"tg://user?id={row['target_id']}"
            try:
                await query.edit_message_text("✅ Rozilik berdingiz. Profilingiz ulashildi.")
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    chat_id=row["requester_id"],
                    text=f"🎉 {row['target_name']} so'rovingizga rozi bo'ldi!\n\nBog'lanish: {contact_line}",
                )
            except Exception as e:
                logger.error(f"Requesterga xabar yuborilmadi: {e}")
        else:
            await client.patch(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"id": f"eq.{req_id}"},
                json={"status": "declined", "responded_at": now_iso},
            )
            try:
                await query.edit_message_text("Rad etdingiz.")
            except Exception:
                pass


# ===== Kogort (guruh) sikli hisoblash =====
COHORT_SIGNUP_DAYS = 5
COHORT_READING_DAYS = 20
COHORT_CLOSING_DAYS = 5


COHORT_SUGGESTED_DAILY_PAGES = 20


def book_reading_days(total_pages):
    if not total_pages or total_pages <= 0:
        return COHORT_READING_DAYS
    return max(1, -(-total_pages // COHORT_SUGGESTED_DAILY_PAGES))


def month_cohort_markers(year: int, month: int):
    days = [1, 5, 10, 15, 20, 25]
    return [dt_date(year, month, d) for d in days]


def nearby_cohort_markers(today: dt_date):
    markers = set()
    for offset in range(-2, 2):
        y = today.year
        m = today.month + offset
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        markers.update(month_cohort_markers(y, m))
    return sorted(markers)


def previous_cohort_marker(marker: dt_date):
    all_markers = []
    for offset in (-1, 0):
        y = marker.year
        m = marker.month + offset
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        all_markers.extend(month_cohort_markers(y, m))
    all_markers.sort()
    idx = all_markers.index(marker) if marker in all_markers else -1
    return all_markers[idx - 1] if idx > 0 else None


def cohort_phase(marker: dt_date, today: dt_date, reading_days: int = None):
    reading_days = reading_days or COHORT_READING_DAYS
    diff = (today - marker).days
    prev_marker = previous_cohort_marker(marker)
    signup_days = (marker - prev_marker).days if prev_marker else COHORT_SIGNUP_DAYS
    if diff < -signup_days:
        return None
    if diff < 0:
        return "signup"
    if diff < reading_days:
        return "reading"
    if diff < reading_days + COHORT_CLOSING_DAYS:
        return "closing"
    return "ended"


def parse_date_str(s: str) -> dt_date:
    return dt_date.fromisoformat(s)


async def check_rank_drops(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            today = datetime.now(timezone.utc).date()

            # ===== KITOB REYTINGI =====
            books_r = await client.get(
                f"{SB_URL}/rest/v1/books",
                headers=SB_HEADERS,
                params={"select": "id,title,total_pages"},
            )
            books = {b["id"]: b for b in books_r.json()}

            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={
                    "select": "book_id,user_id,pages_read,cohort_start_date",
                    "cohort_start_date": "not.is.null",
                    "order": "pages_read.desc",
                },
            )
            all_progress = prog_r.json()
            groups = {}
            for p in all_progress:
                key = (p["book_id"], str(p["cohort_start_date"])[:10])
                groups.setdefault(key, []).append(p)

            for (book_id, cohort_str), members in groups.items():
                marker = parse_date_str(cohort_str)
                book = books.get(book_id)
                if not book:
                    continue
                reading_days = book_reading_days(book.get("total_pages"))
                phase = cohort_phase(marker, today, reading_days)
                if phase not in ("reading", "closing"):
                    continue

                tracker_r = await client.get(
                    f"{SB_URL}/rest/v1/rank_tracker",
                    headers=SB_HEADERS,
                    params={
                        "book_id": f"eq.{book_id}",
                        "cohort_start_date": f"eq.{cohort_str}",
                        "select": "user_id,last_rank",
                    },
                )
                tracker_map = {row["user_id"]: row["last_rank"] for row in tracker_r.json()}

                # TOP 3 o'zgarganini aniqlash
                old_top3 = set(uid for uid, rank in tracker_map.items() if rank <= 3)
                new_top3 = set(p["user_id"] for i, p in enumerate(members) if i < 3)
                top3_changed = old_top3 != new_top3 or any(
                    tracker_map.get(p["user_id"]) != i + 1
                    for i, p in enumerate(members[:3])
                )

                for idx, p in enumerate(members):
                    current_rank = idx + 1
                    uid = p["user_id"]
                    prev_rank = tracker_map.get(uid)
                    if prev_rank is None:
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"🏅 \"{book['title']}\" guruhida siz {current_rank}-o'rindasiz!",
                            )
                        except Exception as e:
                            logger.error(f"Kitob rank xabari yuborilmadi (user_id={uid}): {e}")
                    elif current_rank != prev_rank:
                        arrow = "📈" if current_rank < prev_rank else "📉"
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"{arrow} \"{book['title']}\" guruhida o'riningiz o'zgardi: endi {current_rank}-o'rindasiz.",
                            )
                        except Exception as e:
                            logger.error(f"Kitob rank xabari yuborilmadi (user_id={uid}): {e}")
                    try:
                        await client.post(
                            f"{SB_URL}/rest/v1/rank_tracker?on_conflict=book_id,user_id,cohort_start_date",
                            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
                            json={
                                "book_id": book_id,
                                "user_id": uid,
                                "cohort_start_date": cohort_str,
                                "last_rank": current_rank,
                            },
                        )
                    except Exception as e:
                        logger.error(f"rank_tracker yangilanmadi (book_id={book_id}, user_id={uid}): {e}")

                # TOP 3 o'zgardi — kanalga xabar
                if top3_changed and len(members) >= 1:
                    medals = ["🥇", "🥈", "🥉"]
                    months_uz = ['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr']
                    today_str = f"{today.day}-{months_uz[today.month-1]}, {today.year}"
                    lines = []
                    for i, p in enumerate(members[:3]):
                        lines.append(f"{medals[i]} {p['user_name']} — {p['pages_read']} bet")
                    channel_text = (
                        f"🏆 \"{book['title']}\" TOP 3 yangilandi!\n"
                        f"📅 {today_str}\n\n"
                        + "\n".join(lines) +
                        f"\n\n🌱 Neyra — o'zingni rivojlantir\nt.me/{BOT_USERNAME}/app"
                    )
                    for channel_id in CHANNEL_IDS:
                        try:
                            await context.bot.send_message(chat_id=channel_id, text=channel_text)
                        except Exception as e:
                            logger.error(f"Kanalga kitob TOP3 xabari yuborilmadi: {e}")

    except Exception as e:
        logger.error(f"check_rank_drops xato: {e}")


async def get_all_user_ids(client):
    user_ids = set()
    for table in ("progress", "comments", "finishers"):
        r = await client.get(
            f"{SB_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params={"select": "user_id"},
        )
        for row in r.json():
            uid = row.get("user_id")
            if uid:
                user_ids.add(uid)
    return user_ids


async def send_daily_motivation(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            user_ids = await get_all_user_ids(client)
            text = (
                "Bugun vaqt topib 1 bet bo'lsa ham kitob o'qing, shoshmasdan tushunib o'qing "
                "va o'qiganingizni boshqaga tushuntirib bera oling.\n\n"
                "O'zingizdan faxrlaning, siz kechagidan kuchliroq, aqlliroq siz."
            )
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except Exception as e:
                    logger.error(f"Motivatsiya xabari yuborilmadi (user_id={uid}): {e}")
    except Exception as e:
        logger.error(f"send_daily_motivation xato: {e}")


async def check_join_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/join_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            rows = r.json()
            for row in rows:
                try:
                    book_r = await client.get(
                        f"{SB_URL}/rest/v1/books",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['book_id']}", "select": "title"},
                    )
                    book_rows = book_r.json()
                    title = book_rows[0]["title"] if book_rows else "Kitob"

                    count_r = await client.get(
                        f"{SB_URL}/rest/v1/progress",
                        headers=SB_HEADERS,
                        params={
                            "book_id": f"eq.{row['book_id']}",
                            "cohort_start_date": f"eq.{row['cohort_start_date']}",
                            "select": "user_id",
                        },
                    )
                    total = len(count_r.json())

                    text = (
                        f"📈 {row['cohort_start_date']}da boshlanadigan \"{title}\" o'qish "
                        f"challenjiga yana 1 kishi qo'shildi, jami {total} kishi."
                    )
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Qo'shilish xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/join_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"join_notifications belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_join_notifications xato: {e}")


async def check_join_confirmations(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/join_confirmations",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    share_link = f"https://t.me/{BOT_USERNAME}/app?startapp=book_{row['book_id']}"
                    text = (
                        f"✅ {row['cohort_start_date']}da boshlanadigan \"{row['book_title']}\" "
                        f"challenjiga qo'shildingiz!\n\n"
                        f"Do'stlaringizni ham taklif qiling, ulashish uchun havola:\n{share_link}"
                    )
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"Qo'shilish tasdiqlash xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/join_confirmations",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"join_confirmations belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_join_confirmations xato: {e}")


async def check_payment_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            pr = await client.get(
                f"{SB_URL}/rest/v1/qovun_purchase_requests",
                headers=SB_HEADERS,
                params={"status": "neq.pending", "notified": "eq.false", "select": "*"},
            )
            for row in pr.json():
                try:
                    if row["status"] == "approved":
                        text = f"✅ {row['qovun_amount']} ta qovun sotib olish so'rovingiz tasdiqlandi va hisobingizga qo'shildi."
                    else:
                        reason = row.get("reject_reason") or "sabab ko'rsatilmagan"
                        text = f"❌ {row['qovun_amount']} ta qovun sotib olish so'rovingiz rad etildi. Sabab: {reason}"
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"To'lov xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/qovun_purchase_requests",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"notified": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (purchase id={row.get('id')}): {e}")

            wr = await client.get(
                f"{SB_URL}/rest/v1/withdrawal_requests",
                headers=SB_HEADERS,
                params={"status": "neq.pending", "notified": "eq.false", "select": "*"},
            )
            for row in wr.json():
                try:
                    if row["status"] == "paid":
                        text = (
                            f"✅ {row['amount']} ta {row['currency']} ({row['money_amount']} so'm) "
                            f"pulga aylantirish so'rovingiz to'landi."
                        )
                    else:
                        reason = row.get("reject_reason") or "sabab ko'rsatilmagan"
                        text = f"❌ Pulga aylantirish so'rovingiz rad etildi. Sabab: {reason}"
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"Pul chiqarish xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/withdrawal_requests",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"notified": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (withdrawal id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_payment_notifications xato: {e}")


async def check_book_approval_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/book_approval_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    text = f"✅ \"{row['book_title']}\" kitobingiz admin tomonidan tasdiqlandi va endi ilovada hammaga ko'rinadi!"
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Tasdiqlash xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/book_approval_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (book_approval id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_book_approval_notifications xato: {e}")


async def check_challenge_start(context: ContextTypes.DEFAULT_TYPE):
    """Bugun boshlanayotgan challenj guruhlariga xabar yuborish."""
    try:
        from datetime import timezone as tz
        import pytz
        uzt = pytz.timezone('Asia/Tashkent')
        today = datetime.now(uzt).date()
        months_uz = ['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr']
        today_str = f"{today.day}-{months_uz[today.month-1]}, {today.year}"
        async with httpx.AsyncClient(timeout=30) as client:
            # Kitob challenjlari
            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={"cohort_start_date": f"eq.{today}", "select": "user_id,book_id,cohort_start_date"},
            )
            book_progs = prog_r.json()
            book_ids = list(set(p["book_id"] for p in book_progs))
            for book_id in book_ids:
                book_r = await client.get(
                    f"{SB_URL}/rest/v1/books",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{book_id}", "select": "title,total_pages"},
                )
                books = book_r.json()
                if not books:
                    continue
                book = books[0]
                reading_days = -(-book.get("total_pages", 200) // 20)
                members = [p for p in book_progs if p["book_id"] == book_id]
                pm_text = (
                    f"📖 \"{book['title']}\" kitob challenjingiz bugun boshlandi!\n\n"
                    f"Challenj davomiyligi: {reading_days} kun\n"
                    f"Kunlik me'yor: 20 bet\n\n"
                    f"Muvaffaqiyat! 🌱"
                )
                for member in members:
                    try:
                        await context.bot.send_message(chat_id=member["user_id"], text=pm_text)
                    except Exception as e:
                        logger.error(f"Kitob start xabari yuborilmadi (user_id={member['user_id']}): {e}")
                # Kanalga xabar
                channel_text = (
                    f"📚 Kitob challenjи boshlandi!\n"
                    f"📅 {today_str}\n"
                    f"📖 \"{book['title']}\"\n\n"
                    f"👥 {len(members)} kishi bugun challenjni boshladi!\n\n"
                    f"🌱 Neyra — o'zingni rivojlantir\n"
                    f"t.me/{BOT_USERNAME}/app"
                )
                for channel_id in CHANNEL_IDS:
                    try:
                        await context.bot.send_message(chat_id=channel_id, text=channel_text)
                    except Exception as e:
                        logger.error(f"Kanalga kitob start xabari yuborilmadi (id={channel_id}): {e}")

    except Exception as e:
        logger.error(f"check_challenge_start xato: {e}")


async def send_daily_top(context: ContextTypes.DEFAULT_TYPE):
    """Har kuni 22:00 UZT (17:00 UTC) da kanalga TOP 3 yuborish."""
    try:
        import pytz
        uzt = pytz.timezone('Asia/Tashkent')
        today = datetime.now(uzt).date()
        months_uz = ['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr']
        today_str = f"{today.day}-{months_uz[today.month-1]}, {today.year}"
        medals = ["🥇", "🥈", "🥉"]
        async with httpx.AsyncClient(timeout=30) as client:
            # ===== KITOB TOP 3 =====
            book_lines = []
            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={"select": "user_id,user_name,pages_read,book_id,cohort_start_date", "order": "pages_read.desc"},
            )
            progs = prog_r.json()
            # Faqat bugun "reading" holatidagi guruhlar
            active_progs = []
            for p in progs:
                if not p.get("cohort_start_date"):
                    continue
                cohort_date = dt_date.fromisoformat(p["cohort_start_date"])
                diff = (today - cohort_date).days
                if 0 <= diff < 60:
                    active_progs.append(p)

            if active_progs:
                top_book = active_progs[:3]
                book_r = await client.get(
                    f"{SB_URL}/rest/v1/books",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{active_progs[0]['book_id']}", "select": "title,total_pages"},
                )
                book_info = book_r.json()
                book_title = book_info[0]["title"] if book_info else "Kitob"
                total_pages = book_info[0]["total_pages"] if book_info else 0
                cohort_date_str = active_progs[0]["cohort_start_date"]
                cohort_dt = dt_date.fromisoformat(cohort_date_str)
                cohort_str = f"{cohort_dt.day}-{['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'][cohort_dt.month-1]} guruhi"
                daily_limit = 20
                for i, p in enumerate(top_book):
                    book_lines.append(f"{medals[i]} {p['user_name']} — {p['pages_read']}/{daily_limit} bet")

            sport_lines = []
            # ===== XABAR YARATISH =====
            if not book_lines and not sport_lines:
                return

            msg_parts = [f"📅 {today_str}\n"]
            if book_lines:
                msg_parts.append(f"📚 Kitob challenjida bugungi TOP 3")
                if active_progs:
                    msg_parts.append(f"📖 \"{book_title}\" — {cohort_str}")
                msg_parts.extend(book_lines)
                msg_parts.append("")
            msg_parts.append("🌱 Neyra — o'zingni rivojlantir")
            msg_parts.append(f"t.me/{BOT_USERNAME}/app")

            text = "\n".join(msg_parts)
            for channel_id in CHANNEL_IDS:
                try:
                    await context.bot.send_message(chat_id=channel_id, text=text)
                except Exception as e:
                    logger.error(f"Kanalga xabar yuborilmadi (id={channel_id}): {e}")
    except Exception as e:
        logger.error(f"send_daily_top xato: {e}")


async def check_payment_requests(context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi obuna so'rovlarini tekshirish va invoice yuborish"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/payment_requests?sent=eq.false&select=*&order=created_at.asc",
                headers=SB_HEADERS
            )
            for row in r.json():
                try:
                    await context.bot.send_invoice(
                        chat_id=row['user_id'],
                        title="Neyra — Oylik obuna",
                        description="Neyra ilovasiga 30 kunlik kirish huquqi",
                        payload=f"sub_{row['user_id']}",
                        provider_token="",
                        currency="XTR",
                        prices=[{"label": "Oylik obuna", "amount": SUBSCRIPTION_PRICE}],
                    )
                    await client.patch(
                        f"{SB_URL}/rest/v1/payment_requests",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['id']}"},
                        json={"sent": True}
                    )
                except Exception as e:
                    logger.error(f"Invoice yuborilmadi ({row.get('user_id')}): {e}")
    except Exception as e:
        logger.error(f"check_payment_requests xato: {e}")


# ===== Cheklist eslatmalar =====
# Bugun yuborilgan eslatmalarni saqlash
_sent_reminders_today = set()
_sent_reminders_date = None

async def send_checklist_reminders(context: ContextTypes.DEFAULT_TYPE):
    global _sent_reminders_today, _sent_reminders_date
    import datetime
    now = datetime.datetime.now(pytz.timezone('Asia/Tashkent'))
    today_str = now.strftime('%Y-%m-%d')

    # Yangi kun bo'lsa — tozalash
    if _sent_reminders_date != today_str:
        _sent_reminders_today = set()
        _sent_reminders_date = today_str

    current_day = str(now.isoweekday())
    logger.info(f"[Reminder] Tekshirilmoqda: {now.strftime('%H:%M')} kun={current_day}")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            items_r = await client.get(
                f"{SB_URL}/rest/v1/checklist_items?select=*&is_active=eq.true",
                headers=SB_HEADERS
            )
            items = items_r.json()
            logger.info(f"[Reminder] Jami vazifalar: {len(items)}")
            items_with_reminder = [i for i in items if i.get('reminder_minutes') and i.get('start_time')]
            logger.info(f"[Reminder] Eslatmali vazifalar: {len(items_with_reminder)}")
            logger.info(f"[Reminder] Eslatmali vazifalar: {len(items_with_reminder)}")
            if not items_with_reminder:
                logger.info("[Reminder] Eslatmali vazifa yo'q, o'tkazilmoqda")
                return
            for item in items_with_reminder:
                days = (item.get('days_of_week') or '1,2,3,4,5,6,7').split(',')
                if current_day not in days:
                    continue
                start = datetime.datetime.strptime(item['start_time'], '%H:%M')
                remind_dt = datetime.datetime.combine(datetime.date.today(), start.time()) - datetime.timedelta(minutes=item['reminder_minutes'])
                now_minutes = now.hour * 60 + now.minute
                remind_minutes = remind_dt.hour * 60 + remind_dt.minute
                remind_key = f"{item['id']}_{today_str}_{remind_dt.strftime('%H:%M')}"
                if remind_key in _sent_reminders_today:
                    continue  # Bugun allaqachon yuborilgan

                logger.info(f"[Reminder] {item['title']}: yuborish vaqti={remind_dt.strftime('%H:%M')}, hozir={now.strftime('%H:%M')}, farq={abs(now_minutes - remind_minutes)}")
                if abs(now_minutes - remind_minutes) > 1:
                    continue
                msg = f"🔔 Eslatma: *{item['title']}*\n⏰ {item['start_time']}"
                if item.get('end_time'):
                    msg += f" — {item['end_time']}"
                # Faqat vazifani yaratgan foydalanuvchiga yuborish
                target_uid = item.get('user_id')
                if not target_uid:
                    continue
                logger.info(f"[Reminder] Yuborilmoqda: {item['title']} → uid={target_uid}")
                sent = False
                try:
                    await context.bot.send_message(chat_id=target_uid, text=msg, parse_mode='Markdown')
                    sent = True
                except Exception as ex:
                    logger.warning(f"[Reminder] {target_uid} ga yuborilmadi: {ex}")
                if sent:
                    _sent_reminders_today.add(remind_key)
    except Exception as e:
        logger.error(f"send_checklist_reminders xato: {e}")


# ===== Asosiy =====
# ===== HTTP Server (create_invoice endpoint) =====
class BotHTTPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _json(self, code, data):
        import json
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if parsed.path == "/create_invoice":
            params = parse_qs(parsed.query)
            user_id = params.get("user_id", [None])[0]
            if not user_id:
                self._json(400, {"error": "user_id required"})
                return
            try:
                with httpx.Client(timeout=10) as client:
                    resp = client.post(
                        f"https://api.telegram.org/bot{TOKEN}/createInvoiceLink",
                        json={
                            "title": "Neyra — Oylik obuna",
                            "description": "Neyra ilovasiga 30 kunlik kirish huquqi",
                            "payload": f"sub_{user_id}",
                            "currency": "XTR",
                            "prices": [{"label": "Oylik obuna", "amount": SUBSCRIPTION_PRICE}]
                        }
                    )
                result = resp.json()
                if result.get("ok"):
                    self._json(200, {"link": result["result"]})
                else:
                    logger.error(f"Telegram API xato: {result}")
                    self._json(500, {"error": result.get("description", "Xato")})
            except Exception as e:
                logger.error(f"create_invoice xato: {e}")
                self._json(500, {"error": str(e)})
        else:
            self._json(200, {"status": "ok"})



def run_web_server():
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Veb-server {port}-portda ishga tushirilmoqda...")
    try:
        http.server.ThreadingHTTPServer.allow_reuse_address = True
        httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), BotHTTPHandler)
        logger.info(f"Veb-server {port}-portda muvaffaqiyatli ishga tushdi.")
        httpd.serve_forever()
    except Exception:
        logger.exception("Veb-server ishga tushmadi:")


def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(CallbackQueryHandler(contact_response_callback, pattern=r"^cr_(yes|no)_\d+$"))

    if application.job_queue:
        pass  # Barcha xabarlar vaqtincha to'xtatilgan
        application.job_queue.run_repeating(check_contact_requests, interval=15, first=5)
        application.job_queue.run_repeating(check_rank_drops, interval=30, first=12)
        application.job_queue.run_repeating(check_join_notifications, interval=15, first=10)
        application.job_queue.run_repeating(check_join_confirmations, interval=15, first=11)
        application.job_queue.run_repeating(check_payment_notifications, interval=15, first=13)
        application.job_queue.run_repeating(check_book_approval_notifications, interval=15, first=16)
        application.job_queue.run_repeating(send_checklist_reminders, interval=60, first=20)
        application.job_queue.run_repeating(check_payment_requests, interval=15, first=8)
        # application.job_queue.run_daily(
        #     check_challenge_start,
        #     time=dt_time(23, 0, 0, tzinfo=timezone.utc),  # 04:00 UZT
        # )
        # application.job_queue.run_daily(
        #     send_daily_top,
        #     time=dt_time(17, 0, 0, tzinfo=timezone.utc),  # 22:00 UZT
        # )
    else:
        logger.warning(
            "job_queue mavjud emas. Terminalda quyidagini ishga tushiring: "
            'pip install "python-telegram-bot[job-queue]"'
        )

    logger.info("Bot ishga tushdi.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
