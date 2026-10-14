import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


def make_callback_query(cb_data: str, from_username: str | None = None):
    """Создаёт мок CallbackQuery с нужными полями."""
    cb = MagicMock()
    cb.data = cb_data
    cb.from_user = MagicMock()
    cb.from_user.username = from_username
    cb.message = MagicMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = -100
    cb.message.message_id = 1
    cb.answer = AsyncMock()
    return cb


def make_message(text: str, from_username: str | None = "alisandrii"):
    msg = MagicMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.username = from_username
    msg.chat = MagicMock()
    msg.chat.id = -100
    msg.answer = AsyncMock()
    return msg


@pytest.fixture
def mock_bot():
    with patch("bot.bot") as b:
        b.send_message = AsyncMock()
        b.edit_message_reply_markup = AsyncMock()
        yield b


@pytest.fixture
def gift_db():
    """БД для callback выбора подарка: подарок ещё не выбран."""
    with patch("bot.save_gift_by_username", AsyncMock()) as save, \
         patch("bot.get_gift_by_username", AsyncMock(return_value=None)) as get, \
         patch("bot.get_birthday_by_username", AsyncMock(return_value="21.03")), \
         patch("bot.get_chats", AsyncMock(return_value=[-100, -200])):
        yield save, get


@pytest.fixture(autouse=True)
def clear_pending_gift_messages():
    import app.scheduler as sched
    sched.pending_gift_messages.clear()
    yield
    sched.pending_gift_messages.clear()


# --- выбор подарка ---

async def test_choose_gift_wrong_user_shows_alert(gift_db, mock_bot):
    """Пользователь, который не является именинником, получает алерт."""
    save, _ = gift_db
    cb = make_callback_query("gift|alice12345|embroidery|2026", from_username="bob12345")

    from bot import choose_gift
    await choose_gift(cb)

    assert cb.answer.call_args.kwargs.get("show_alert") is True
    save.assert_not_called()


async def test_choose_gift_no_username_shows_alert(gift_db, mock_bot):
    """Пользователь без username получает алерт."""
    cb = make_callback_query("gift|alice12345|embroidery|2026", from_username=None)

    from bot import choose_gift
    await choose_gift(cb)

    assert cb.answer.call_args.kwargs.get("show_alert") is True


async def test_choose_gift_saves_and_notifies(gift_db, mock_bot):
    """Именинник делает выбор — подарок сохраняется на нужный год, в чаты уходит понятное название."""
    save, _ = gift_db
    cb = make_callback_query("gift|alice12345|money|2026", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    save.assert_called_once_with("alice12345", "money", 2026)
    assert mock_bot.send_message.call_count == 2
    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "💸 Деньги" in text
    assert "money" not in text
    cb.answer.assert_called_once_with("Готово")


async def test_choose_gift_legacy_button_without_year(gift_db, mock_bot):
    """Кнопки, отправленные старой версией (без года), продолжают работать."""
    save, _ = gift_db
    cb = make_callback_query("gift|alice12345|embroidery", from_username="alice12345")

    with patch("bot.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 3, 18)
        from bot import choose_gift
        await choose_gift(cb)

    save.assert_called_once_with("alice12345", "embroidery", 2026)


async def test_choose_gift_already_chosen(gift_db, mock_bot):
    """Повторное нажатие (например, на старой кнопке после рестарта) не перезаписывает выбор."""
    save, get = gift_db
    get.return_value = "money"
    cb = make_callback_query("gift|alice12345|embroidery|2026", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    save.assert_not_called()
    mock_bot.send_message.assert_not_called()
    mock_bot.edit_message_reply_markup.assert_called_once_with(
        chat_id=-100, message_id=1, reply_markup=None
    )


async def test_choose_gift_unknown_choice_ignored(gift_db, mock_bot):
    """Подделанный вариант подарка не сохраняется."""
    save, _ = gift_db
    cb = make_callback_query("gift|alice12345|car|2026", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    save.assert_not_called()


async def test_choose_gift_clears_all_pending_keyboards(gift_db, mock_bot):
    """После выбора клавиатура убирается из всех сохранённых сообщений и из нажатого."""
    import app.scheduler as sched
    sched.pending_gift_messages["alice12345"] = [(-100, 10), (-200, 20)]

    cb = make_callback_query("gift|alice12345|embroidery|2026", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    edited = {(c.kwargs["chat_id"], c.kwargs["message_id"])
              for c in mock_bot.edit_message_reply_markup.call_args_list}
    assert edited == {(-100, 10), (-200, 20), (-100, 1)}
    assert "alice12345" not in sched.pending_gift_messages


async def test_choose_gift_notify_error_doesnt_break(gift_db, mock_bot):
    """Ошибка при отправке уведомления не ломает весь callback."""
    mock_bot.send_message = AsyncMock(side_effect=Exception("network error"))
    cb = make_callback_query("gift|alice12345|money|2026", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    cb.answer.assert_called_once_with("Готово")


async def test_choose_gift_malformed_data():
    """Кривые данные в callback_data обрабатываются без краша."""
    cb = make_callback_query("gift|onlytwoparts", from_username="alice12345")

    from bot import choose_gift
    await choose_gift(cb)

    cb.answer.assert_called_once()


# --- права админов ---

@pytest.mark.parametrize("handler_name,text", [
    ("add_birthday_cmd", "/add @alice12345 21.03"),
    ("remove_birthday_cmd", "/remove @alice12345"),
    ("seed", "/seed"),
    ("test", "/test"),
    ("count_cmd", "/count"),
    ("dbpath", "/dbpath"),
])
async def test_admin_commands_denied_for_others(handler_name, text):
    import bot
    msg = make_message(text, from_username="randomuser")

    with patch("bot.save_birthday", AsyncMock()) as save, \
         patch("bot.delete_birthday", AsyncMock()) as delete, \
         patch("bot.run_import_birthdays", AsyncMock()) as imp, \
         patch("bot.send_reminders", AsyncMock()) as remind:
        await getattr(bot, handler_name)(msg)

    msg.answer.assert_called_once_with("Эта команда только для админов")
    for m in (save, delete, imp, remind):
        m.assert_not_called()


@pytest.mark.parametrize("username", ["alisandrii", "FiraSakhapova"])
async def test_add_allowed_for_admins(username):
    from bot import add_birthday_cmd
    msg = make_message("/add @alice12345 21.03", from_username=username)

    with patch("bot.save_birthday", AsyncMock()) as save:
        await add_birthday_cmd(msg)

    save.assert_called_once_with("alice12345", "21.03")


async def test_add_rejects_invalid_date():
    from bot import add_birthday_cmd
    msg = make_message("/add @alice12345 31.02")

    with patch("bot.save_birthday", AsyncMock()) as save:
        await add_birthday_cmd(msg)

    save.assert_not_called()
    assert "Некорректная дата" in msg.answer.call_args.args[0]


async def test_remove_birthday():
    from bot import remove_birthday_cmd
    msg = make_message("/remove @alice12345")

    with patch("bot.delete_birthday", AsyncMock(return_value=True)) as delete:
        await remove_birthday_cmd(msg)

    delete.assert_called_once_with("alice12345")
    msg.answer.assert_called_once_with("ДР @alice12345 удалён")


# --- команды для всех ---

async def test_when_available_for_everyone():
    from bot import when_birthday
    msg = make_message("/when @alice12345", from_username="randomuser")

    with patch("bot.get_birthday_by_username", AsyncMock(return_value="25.03")), \
         patch("bot.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 3, 21)
        await when_birthday(msg)

    msg.answer.assert_called_once_with("ДР @alice12345: 25.03 (через 4 дня)")


async def test_month_available_for_everyone():
    from bot import month_birthdays
    msg = make_message("/month", from_username="randomuser")

    with patch("bot.get_birthdays_in_month", AsyncMock(return_value=[("bob12345", "25.03"), ("alice12345", "02.03")])), \
         patch("bot.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 3, 21)
        await month_birthdays(msg)

    msg.answer.assert_called_once_with("Дни рождения — Март:\n02.03 — @alice12345\n25.03 — @bob12345")


async def test_upcoming():
    from bot import upcoming_birthdays
    msg = make_message("/upcoming", from_username="randomuser")

    rows = [("bob12345", "25.03"), ("alice12345", "21.03"), ("far12345", "01.09")]
    with patch("bot.get_birthdays", AsyncMock(return_value=rows)), \
         patch("bot.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 3, 21)
        await upcoming_birthdays(msg)

    msg.answer.assert_called_once_with(
        "Ближайшие дни рождения:\n"
        "21.03 — @alice12345 (сегодня 🎉)\n"
        "25.03 — @bob12345 (через 4 дня)"
    )
