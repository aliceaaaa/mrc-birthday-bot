import asyncio
import re
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN
from db import init_db, save_birthday, save_gift_by_username, save_chat, get_chats, get_birthdays_in_month, count_birthdays, get_birthday_by_username
from app.scheduler import start_scheduler, send_reminders
from core.utils import normalize_date_or_none, normalize_username_or_none
from scripts.import_birthdays import run_import_birthdays
import os

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "Я напомню о днях рождения.\n"
        "Команды:\n"
        "/add @username DD.MM — добавить ДР\n"
        "/month — ДР в этом месяце\n"
        "/when @username — когда ДР\n"
        "/test — отправить тестовые напоминания\n"
        "/seed — импорт исходных данных\n"
        "/count — показать кол-во записей\n"
        "/dbpath — путь к БД"
    )

@dp.message(Command("add"))
async def add_birthday_cmd(msg: types.Message):
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
        await msg.answer("Некорректная дата")
        return
    
    await save_birthday(user, d)
    await msg.answer(f"ДР @{user} сохранён: {d}")

@dp.message(Command("month"))
async def month_birthdays(msg: types.Message):
    today = date.today()
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
    month_names = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь", 7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}
    title = month_names.get(today.month, "")
    lines = [f"Дни рождения — {title}:"]
    for _, uname, d in items:
        at = f"@{uname}" if uname else ""
        lines.append(f"{d} — {at}".rstrip())
    await msg.answer("\n".join(lines))

@dp.message(Command("when"))
async def when_birthday(msg: types.Message):
    parts = msg.text.split() if msg.text else []
    
    if len(parts) != 2:
        await msg.answer("Формат: /when @username")
        return
    
    raw = parts[1].strip()
    if raw.startswith("@"):
        raw = raw[1:]
    user = normalize_username_or_none(raw)
    
    if not user:
        await msg.answer("Некорректный @username")
        return
    
    d = await get_birthday_by_username(user)
    if not d:
        await msg.answer(f"ДР для @{user} не найден")
        return
    
    today = date.today()
    day, month = map(int, d.split("."))
    try:
        b = date(today.year, month, day)
    except ValueError:
        if month == 2 and day == 29:
            b = date(today.year, 2, 28)
        else:
            await msg.answer(f"Дата в базе некорректна: {d}")
            return
    if b < today:
        try:
            b = b.replace(year=today.year + 1)
        except ValueError:
            if month == 2 and day == 29:
                b = date(today.year + 1, 2, 28)
            else:
                await msg.answer(f"Дата в базе некорректна: {d}")
                return
    delta = (b - today).days
    if delta == 0:
        text = f"Сегодня ДР у @{user} 🎉 ({d})"
    elif delta == 1:
        text = f"Завтра ДР у @{user} ({d})"
    else:
        text = f"ДР @{user}: {d} (через {delta} дней)"
    await msg.answer(text)

@dp.callback_query(lambda cb: cb.data and cb.data.startswith("gift|"))
async def choose_gift(cb: types.CallbackQuery):
    _, tg_username, choice = cb.data.split("|", 2) if cb.data else ""
    
    await save_gift_by_username(tg_username, choice)
    
    chats = await get_chats()
    
    for chat_id in chats:
        await bot.send_message(chat_id, f"@{tg_username} выбрал подарок: {choice}")
   
    if cb.message:
        await bot.edit_message_reply_markup(
            chat_id=cb.message.chat.id,
            message_id=cb.message.message_id,
            reply_markup=None
        )
        
    await cb.answer("Готово")

@dp.message(Command("test"))
async def test(msg: types.Message):
    await send_reminders(bot)
    await msg.answer("Отправил тестовые напоминания")

@dp.message(Command("seed"))
async def seed(msg: types.Message):
    ins, upd = await run_import_birthdays()
    await msg.answer(f"Импорт завершён: добавлено {ins}, обновлено {upd}")

@dp.message(Command("count"))
async def count_cmd(msg: types.Message):
    n = await count_birthdays()
    await msg.answer(f"birthdays={n}")

@dp.message(Command("dbpath"))
async def dbpath(msg: types.Message):
    from db import DB_NAME
    await msg.answer(f"DB_PATH={os.environ.get('DB_PATH','(not set)')}\nDB_NAME={DB_NAME}")

@dp.message()
async def register_chat(msg: types.Message):
    await save_chat(msg.chat.id)

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    if await count_birthdays() == 0:
        await run_import_birthdays()
        
    start_scheduler(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
