from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, timezone, timedelta, datetime

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Tbilisi")
except Exception:
    TZ = timezone(timedelta(hours=4), name="Asia/Tbilisi")

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import get_birthdays, get_chats

scheduler = AsyncIOScheduler(timezone=TZ)

def start_scheduler(bot):
    scheduler.add_job(
        send_reminders,
        "cron",
        hour=9,
        minute=00,
        second=0,
        args=[bot],
        id="daily_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()


async def send_reminders(bot, force: bool = False, target_chat_id: int | None = None):
    birthdays = await get_birthdays()
    chats = [target_chat_id] if target_chat_id else await get_chats()
    today = datetime.now(TZ).date()
    sent = 0
    failed = 0

    for tg_username, date_str in birthdays:
        try:
            day, month = map(int, date_str.split("."))
        except Exception:
            failed += 1
            continue

        try:
            birthday = date(today.year, month, day)
        except ValueError:
            if month == 2 and day == 29:
                birthday = date(today.year, 2, 28)
            else:
                failed += 1
                continue

        if birthday < today:
            try:
                birthday = birthday.replace(year=today.year + 1)
            except ValueError:
                if month == 2 and day == 29:
                    birthday = date(today.year + 1, 2, 28)
                else:
                    failed += 1
                    continue

        delta = (birthday - today).days
        if not force and delta not in (7, 1, 0):
            continue

        if delta == 7:
            text = f"Через 7 дней ДР у @{tg_username}"
        elif delta == 1:
            text = f"Завтра ДР у @{tg_username}"
        elif delta == 0:
            text = f"Сегодня ДР у @{tg_username} 🎉"
        else:
            text = f"Тест: ДР у @{tg_username} {date_str}"

        keyboard = None
        if tg_username:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🎁 Вышивка",
                            callback_data=f"gift|{tg_username}|embroidery"
                        ),
                        InlineKeyboardButton(
                            text="💸 Деньги",
                            callback_data=f"gift|{tg_username}|money"
                        )
                    ]
                ]
            )

        if not force and delta == 7 and tg_username:
            try:
                await bot.send_message(
                    chat_id=f"@{tg_username}",
                    text="Скоро у тебя день рождения 🎉\nКакой подарок ты бы хотел?",
                    reply_markup=keyboard
                )
            except Exception:
                failed += 1

        for chat_id in chats:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
                sent += 1
            except Exception:
                failed += 1

    return sent, failed
