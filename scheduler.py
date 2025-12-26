from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import get_birthdays, get_chats

scheduler = AsyncIOScheduler()

def start_scheduler(bot):
    scheduler.add_job(
        send_reminders,
        "cron",
        hour=10,
        args=[bot]
    )
    scheduler.start()

async def send_reminders(bot):
    birthdays = await get_birthdays()
    chats = await get_chats()

    for tg_username, date_str in birthdays:
        day, month = map(int, date_str.split("."))
        today = date.today()
        birthday = date(today.year, month, day)
        delta = (birthday - today).days

        if delta not in (7, 1, 0):
            continue

        text = (
            f"Через 7 дней ДР у @{tg_username}"
            if delta == 7 else
            f"Завтра ДР у @{tg_username}"
            if delta == 1 else
            f"Сегодня ДР у @{tg_username} 🎉"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎁 Вышивка",
                        callback_data=f"gift_{tg_username}_embroidery"
                    ),
                    InlineKeyboardButton(
                        text="💸 Деньги",
                        callback_data=f"gift_{tg_username}_money"
                    )
                ]
            ]
        )

        if delta == 7 and tg_username:
            await bot.send_message(
                chat_id=f"@{tg_username}",
                text="Скоро у тебя день рождения 🎉\nКакой подарок ты бы хотел?",
                reply_markup=keyboard
            )

        for chat_id in chats:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard
            )
