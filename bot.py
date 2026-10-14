import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logging.getLogger("aiogram").setLevel(logging.INFO)
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)

import asyncio
from typing import Any, Awaitable, Callable
from datetime import datetime
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import TelegramObject
from config import ADMIN_USERNAMES, BOT_TOKEN
from db import (
    init_db,
    save_birthday,
    delete_birthday,
    save_gift_by_username,
    get_gift_by_username,
    save_chat,
    get_chats,
    get_birthdays,
    get_birthdays_in_month,
    count_birthdays,
    get_birthday_by_username,
)
from app.scheduler import (
    GIFT_OPTIONS,
    pending_gift_messages,
    safe_send,
    send_reminders,
    start_scheduler,
)
from core.utils import (
    TZ,
    days_word,
    gift_year,
    next_birthday,
    normalize_date_or_none,
    normalize_username_or_none,
)
from scripts.import_birthdays import run_import_birthdays

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


class SaveChatMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, types.Message):
            await save_chat(event.chat.id)
        return await handler(event, data)

dp.message.middleware(SaveChatMiddleware())


def is_admin(user: types.User | None) -> bool:
    return normalize_username_or_none(user.username if user else None) in ADMIN_USERNAMES


async def require_admin(msg: types.Message) -> bool:
    if is_admin(msg.from_user):
        return True
    await msg.answer("Эта команда только для админов")
    return False


def when_text(delta: int) -> str:
    if delta == 0:
        return "сегодня 🎉"
    if delta == 1:
        return "завтра"
    return f"через {delta} {days_word(delta)}"


@dp.message(Command("ping"))
async def ping(msg: types.Message):
    await msg.answer("pong")


@dp.message(Command("start", "help"))
async def start(msg: types.Message):
    text = (
        "Я напомню о днях рождения.\n"
        "Команды:\n"
        "/month — ДР в этом месяце\n"
        "/when @username — когда ДР\n"
        "/upcoming — ДР в ближайшие 30 дней"
    )
    if is_admin(msg.from_user):
        text += (
            "\n\nДля админов:\n"
            "/add @username DD.MM — добавить или изменить ДР\n"
            "/remove @username — удалить ДР\n"
            "/test — тестовое напоминание\n"
            "/seed — импорт исходных данных\n"
            "/count — сколько ДР в базе\n"
            "/dbpath — какая БД подключена"
        )
    await msg.answer(text)


@dp.message(Command("add"))
async def add_birthday_cmd(msg: types.Message):
    if not await require_admin(msg):
        return

    parts = msg.text.split() if msg.text else []

    if len(parts) != 3:
        await msg.answer("Формат: /add @username DD.MM")
        return

    user = normalize_username_or_none(parts[1])
    d = normalize_date_or_none(parts[2])

    if not user:
        await msg.answer("Некорректный @username")
        return

    if not d:
        await msg.answer("Некорректная дата, нужен формат DD.MM, например 05.09")
        return

    await save_birthday(user, d)
    await msg.answer(f"ДР @{user} сохранён: {d}")


@dp.message(Command("remove"))
async def remove_birthday_cmd(msg: types.Message):
    if not await require_admin(msg):
        return

    parts = msg.text.split() if msg.text else []

    if len(parts) != 2:
        await msg.answer("Формат: /remove @username")
        return

    user = normalize_username_or_none(parts[1])
    if not user:
        await msg.answer("Некорректный @username")
        return

    if await delete_birthday(user):
        await msg.answer(f"ДР @{user} удалён")
    else:
        await msg.answer(f"ДР для @{user} не найден")


@dp.message(Command("month"))
async def month_birthdays(msg: types.Message):
    today = datetime.now(TZ).date()
    rows = await get_birthdays_in_month(today.month)
    items = []
    for uname, d in rows:
        if not d or len(d) != 5:
            continue
        try:
            day_i = int(d[:2])
        except ValueError:
            continue
        items.append((day_i, uname or "", d))
    items.sort(key=lambda x: x[0])
    if not items:
        await msg.answer("В этом месяце дней рождения нет")
        return
    title = MONTH_NAMES.get(today.month, "")
    lines = [f"Дни рождения — {title}:"]
    for _, uname, d in items:
        at = f"@{uname}" if uname else ""
        lines.append(f"{d} — {at}".rstrip())
    await msg.answer("\n".join(lines))


@dp.message(Command("upcoming"))
async def upcoming_birthdays(msg: types.Message):
    today = datetime.now(TZ).date()
    items = []
    for uname, d in await get_birthdays():
        b = next_birthday(d, today)
        if b is None:
            continue
        delta = (b - today).days
        if delta <= 30:
            items.append((delta, uname or "", d))
    if not items:
        await msg.answer("В ближайшие 30 дней дней рождения нет")
        return
    items.sort()
    lines = ["Ближайшие дни рождения:"]
    for delta, uname, d in items:
        lines.append(f"{d} — @{uname} ({when_text(delta)})")
    await msg.answer("\n".join(lines))


@dp.message(Command("when"))
async def when_birthday(msg: types.Message):
    parts = msg.text.split() if msg.text else []

    if len(parts) != 2:
        await msg.answer("Формат: /when @username")
        return

    user = normalize_username_or_none(parts[1])

    if not user:
        await msg.answer("Некорректный @username")
        return

    d = await get_birthday_by_username(user)
    if not d:
        await msg.answer(f"ДР для @{user} не найден")
        return

    today = datetime.now(TZ).date()
    b = next_birthday(d, today)
    if b is None:
        await msg.answer(f"Дата в базе некорректна: {d}")
        return

    delta = (b - today).days
    if delta == 0:
        text = f"Сегодня ДР у @{user} 🎉 ({d})"
    elif delta == 1:
        text = f"Завтра ДР у @{user} ({d})"
    else:
        text = f"ДР @{user}: {d} ({when_text(delta)})"
    await msg.answer(text)


async def _clear_gift_keyboards(target: str, cb: types.CallbackQuery):
    messages_to_clear = pending_gift_messages.pop(target, [])
    if cb.message:
        messages_to_clear.append((cb.message.chat.id, cb.message.message_id))
    for chat_id, message_id in set(messages_to_clear):
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None
            )
        except Exception:
            pass


@dp.callback_query(lambda cb: cb.data and cb.data.startswith("gift|"))
async def choose_gift(cb: types.CallbackQuery):
    # gift|username|choice|year (у кнопок, отправленных старой версией, года нет)
    parts = cb.data.split("|") if cb.data else []
    if len(parts) not in (3, 4) or parts[2] not in GIFT_OPTIONS:
        await cb.answer()
        return
    raw_username, choice = parts[1], parts[2]

    target = normalize_username_or_none(raw_username) or ""
    clicker = normalize_username_or_none(cb.from_user.username) or ""

    if not clicker or clicker != target:
        await cb.answer(f"Эта кнопка только для @{target}", show_alert=True)
        return

    if len(parts) == 4 and parts[3].isdigit():
        year = int(parts[3])
    else:
        year = gift_year(await get_birthday_by_username(target), datetime.now(TZ).date())

    if await get_gift_by_username(target, year):
        await _clear_gift_keyboards(target, cb)
        await cb.answer("Подарок уже выбран", show_alert=True)
        return

    await save_gift_by_username(target, choice, year)

    for chat_id in await get_chats():
        await safe_send(bot, chat_id, f"@{target} хочет в подарок: {GIFT_OPTIONS[choice]}")

    await _clear_gift_keyboards(target, cb)
    await cb.answer("Готово")


@dp.message(Command("test"))
async def test(msg: types.Message):
    if not await require_admin(msg):
        return
    s, f = await send_reminders(bot, force=True, target_chat_id=msg.chat.id)
    if f or not s:
        await msg.answer(f"Тест: отправлено {s}, ошибок {f}")


@dp.message(Command("seed"))
async def seed(msg: types.Message):
    if not await require_admin(msg):
        return
    ins, upd = await run_import_birthdays()
    await msg.answer(f"Импорт завершён: добавлено {ins}, обновлено {upd}")


@dp.message(Command("count"))
async def count_cmd(msg: types.Message):
    if not await require_admin(msg):
        return
    n = await count_birthdays()
    await msg.answer(f"Дней рождения в базе: {n}")


@dp.message(Command("dbpath"))
async def dbpath(msg: types.Message):
    if not await require_admin(msg):
        return
    from db import DATABASE_URL
    val = "(not set)"
    if DATABASE_URL:
        h = DATABASE_URL.split("@")[-1]
        h = h.split("/")[0]
        val = f"(set, host={h})"
    await msg.answer(f"DATABASE_URL={val}")


async def main():
    # Без базы бот бесполезен — падаем сразу, платформа перезапустит
    await init_db()

    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logging.info("BOT READY: @%s (id=%s)", me.username, me.id)

    try:
        if await count_birthdays() == 0:
            ins, upd = await run_import_birthdays()
            logging.info("SEED: inserted=%s updated=%s", ins, upd)
    except Exception:
        logging.exception("seed failed")

    start_scheduler(bot)
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )

if __name__ == "__main__":
    asyncio.run(main())
