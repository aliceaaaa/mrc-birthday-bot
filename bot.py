import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN
from db import init_db, save_birthday, save_gift, save_chat
from scheduler import start_scheduler

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "Я напомню о днях рождения.\n"
        "Команды:\n"
        "/add DD.MM — добавить ДР"
    )


@dp.message(Command("add"))
async def add_birthday(msg: types.Message):
    parts = msg.text.split() if msg.text else []

    if len(parts) != 3:
        await msg.answer("Формат: /add @username DD.MM")
        return

    tg_username = parts[1].lstrip("@")
    date_str = parts[2]

    if not re.fullmatch(r"\d{2}\.\d{2}", date_str):
        await msg.answer("Формат даты: DD.MM")
        return

    await save_birthday(
        tg_username=tg_username,
        date_str=date_str
    )

    await msg.answer(f"ДР @{tg_username} сохранён: {date_str}")

  
@dp.message()
async def register_chat(msg: types.Message):
    await save_chat(msg.chat.id)
    
from db import get_chats

@dp.callback_query(lambda cb: cb.data and cb.data.startswith("gift_"))
async def choose_gift(cb: types.CallbackQuery):
    _, tg_username, choice = cb.data.split("_") if cb.data else ""

    await save_gift(tg_username, choice)

    chats = await get_chats()
    for chat_id in chats:
        await bot.send_message(
            chat_id=chat_id,
            text=f"@{tg_username} выбрал подарок: {choice}"
        )

    if cb.message:
        await bot.edit_message_reply_markup(
            chat_id=cb.message.chat.id,
            message_id=cb.message.message_id,
            reply_markup=None
        )

    await cb.answer("Готово")



async def main():
    await init_db()
    start_scheduler(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
