import asyncio
from datetime import datetime

import pytz
from telegram import Bot
from telegram.ext import Application

TOKEN = "8780693245:AAENyEtQ2DDidajLdDaOeKuZKg0nniGI4zw"

CHAT_ID = "1645167548"

timezone = pytz.timezone("Asia/Tashkent")


async def send_graphic_reminder(context):
    now = datetime.now(timezone).strftime("%H:%M:%S")

    message = f"""
📊 Grafikni tekshir

🕒 Vaqt: {now}

❗️Savdoga kirishdan oldin:
- Trendni tekshir
- Newsni tekshir
- Riskni hisobla
"""

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=message
    )


async def start_bot():
    app = Application.builder().token(TOKEN).build()

    job_queue = app.job_queue

    # Har 1 minutda yuboradi
    job_queue.run_repeating(
        send_graphic_reminder,
        interval=60,
        first=5
    )

    print("Bot ishladi ✅")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(start_bot())
