import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Tuple

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.utils import TZ, days_word, next_birthday
from db import get_birthdays, get_chats, get_gift_by_username, get_state, set_state

log = logging.getLogger(__name__)

REMINDER_TIME = time(9, 0)
LAST_RUN_KEY = "last_reminders_day"

GIFT_OPTIONS = {
    "embroidery": "🎁 Вышивка",
    "money": "💸 Деньги",
}

# Сообщения с кнопками выбора подарка: username -> [(chat_id, message_id)]
pending_gift_messages: Dict[str, List[Tuple[int, int]]] = {}

scheduler = AsyncIOScheduler(timezone=TZ)
_daily_lock = asyncio.Lock()


async def safe_send(bot, chat_id: int, text: str, reply_markup=None):
    """Отправляет сообщение, переживая flood-лимиты Telegram. None — если не вышло."""
    for _ in range(3):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except TelegramRetryAfter as e:
            log.warning("flood limit in chat %s, waiting %ss", chat_id, e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            log.exception("send_message to %s failed", chat_id)
            return None
    return None


def gift_keyboard(tg_username: str, year: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=label, callback_data=f"gift|{tg_username}|{key}|{year}")
            for key, label in GIFT_OPTIONS.items()
        ]]
    )


def start_scheduler(bot):
    scheduler.add_job(
        daily_reminders,
        "cron",
        hour=REMINDER_TIME.hour,
        minute=REMINDER_TIME.minute,
        second=0,
        args=[bot],
        id="daily_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    # Если бот стартовал после 9:00 и сегодня ещё не рассылал — досылаем сразу
    scheduler.add_job(catch_up_missed_run, args=[bot], id="catch_up", replace_existing=True)
    scheduler.start()


async def daily_reminders(bot):
    async with _daily_lock:
        today = datetime.now(TZ).date().isoformat()
        if await get_state(LAST_RUN_KEY) == today:
            log.info("reminders for %s already sent", today)
            return
        sent, failed = await send_reminders(bot)
        await set_state(LAST_RUN_KEY, today)
        log.info("reminders for %s: sent=%s failed=%s", today, sent, failed)


async def catch_up_missed_run(bot):
    now = datetime.now(TZ)
    if now.time() < REMINDER_TIME:
        return
    last = await get_state(LAST_RUN_KEY)
    if last is None:
        # Первый запуск с этой проверкой: сегодняшнюю рассылку, скорее всего,
        # уже сделала предыдущая версия бота — не дублируем.
        await set_state(LAST_RUN_KEY, now.date().isoformat())
        return
    if last < now.date().isoformat():
        await daily_reminders(bot)


async def send_reminders(bot, force: bool = False, target_chat_id: int | None = None):
    birthdays = await get_birthdays()
    chats = [target_chat_id] if target_chat_id else await get_chats()
    today = datetime.now(TZ).date()
    sent = 0
    failed = 0
    upcoming = []

    for tg_username, date_str in birthdays:
        birthday = next_birthday(date_str, today)
        if birthday is None:
            failed += 1
            continue

        delta = (birthday - today).days

        if force:
            upcoming.append((delta, tg_username or "", date_str))
            continue

        if delta not in (7, 1, 0):
            continue

        if delta == 7:
            text = f"Через 7 дней ДР у @{tg_username}"
        elif delta == 1:
            text = f"Завтра ДР у @{tg_username}"
        else:
            text = f"Сегодня ДР у @{tg_username} 🎉"

        keyboard = None
        if tg_username and not await get_gift_by_username(tg_username, birthday.year):
            text += "\n\nИменинник, выбери подарок 👇"
            keyboard = gift_keyboard(tg_username, birthday.year)

        for chat_id in chats:
            msg = await safe_send(bot, chat_id, text, reply_markup=keyboard)
            if msg is None:
                failed += 1
                continue
            sent += 1
            if keyboard:
                pending_gift_messages.setdefault(tg_username, []).append(
                    (chat_id, msg.message_id)
                )

    if force and upcoming:
        # Тест — одним сообщением и без кнопок, чтобы не упереться в лимиты
        # Telegram и не записать настоящий выбор подарка
        upcoming.sort()
        lines = ["Тест напоминаний. Ближайшие ДР:"]
        for delta, uname, date_str in upcoming:
            when = "сегодня" if delta == 0 else f"через {delta} {days_word(delta)}"
            lines.append(f"{date_str} — @{uname} ({when})")
        for chat_id in chats:
            for chunk in _chunks(lines):
                if await safe_send(bot, chat_id, chunk) is None:
                    failed += 1
                else:
                    sent += 1

    return sent, failed


def _chunks(lines: list[str], limit: int = 4000) -> list[str]:
    """Режет список строк на сообщения не длиннее лимита Telegram."""
    chunks, cur = [], ""
    for line in lines:
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks
