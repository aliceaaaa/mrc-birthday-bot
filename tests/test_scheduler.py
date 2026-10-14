import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramRetryAfter

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 3, 21)


@pytest.fixture(autouse=True)
def clear_pending_gift_messages():
    """Очищаем глобальный dict между тестами."""
    import app.scheduler as sched
    sched.pending_gift_messages.clear()
    yield
    sched.pending_gift_messages.clear()


def make_bot(message_id=42):
    bot = AsyncMock()
    sent_msg = MagicMock()
    sent_msg.message_id = message_id
    bot.send_message = AsyncMock(return_value=sent_msg)
    return bot


def patch_db(birthdays, chats=(-100,), gift=None):
    return (
        patch("app.scheduler.get_birthdays", AsyncMock(return_value=birthdays)),
        patch("app.scheduler.get_chats", AsyncMock(return_value=list(chats))),
        patch("app.scheduler.get_gift_by_username", AsyncMock(return_value=gift)),
    )


async def _send_reminders(bot, birthdays, chats=(-100,), gift=None, force=False, target_chat_id=None):
    from app.scheduler import send_reminders
    p1, p2, p3 = patch_db(birthdays, chats, gift)
    with p1, p2, p3 as mock_gift, patch("app.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = TODAY
        result = await send_reminders(bot, force=force, target_chat_id=target_chat_id)
    return result, mock_gift


async def test_force_sends_one_combined_message():
    """force=True — все ДР одним сообщением, отсортированные по близости, без кнопок."""
    bot = make_bot()

    (sent, failed), _ = await _send_reminders(
        bot, [("bob12345", "15.06"), ("alice12345", "21.03")], force=True
    )

    assert (sent, failed) == (1, 0)
    bot.send_message.assert_called_once()
    kwargs = bot.send_message.call_args.kwargs
    assert kwargs["reply_markup"] is None
    text = kwargs["text"]
    assert text.index("@alice12345") < text.index("@bob12345")
    assert "сегодня" in text


async def test_no_force_sends_only_matching_delta():
    """force=False — ничего не отправляет, если delta не 7, 1 или 0."""
    bot = make_bot()

    (sent, failed), _ = await _send_reminders(bot, [("alice12345", "26.03")])

    assert sent == 0
    bot.send_message.assert_not_called()


@pytest.mark.parametrize("date_str,expected", [
    ("28.03", "Через 7 дней"),
    ("22.03", "Завтра"),
    ("21.03", "Сегодня"),
])
async def test_no_force_sends_on_matching_delta(date_str, expected):
    bot = make_bot()

    (sent, failed), _ = await _send_reminders(bot, [("alice12345", date_str)])

    assert (sent, failed) == (1, 0)
    assert bot.send_message.call_args.kwargs["text"].startswith(expected)


async def test_no_direct_message_to_username():
    """Бот не пытается писать имениннику в личку по @username."""
    bot = make_bot()

    await _send_reminders(bot, [("alice12345", "28.03")])

    chat_ids = [c.kwargs["chat_id"] for c in bot.send_message.call_args_list]
    assert chat_ids == [-100]


async def test_keyboard_attached_when_no_gift():
    """Клавиатура прикрепляется, если подарок в этом году ещё не выбран."""
    bot = make_bot()

    _, mock_gift = await _send_reminders(bot, [("alice12345", "21.03")])

    keyboard = bot.send_message.call_args.kwargs.get("reply_markup")
    assert keyboard is not None
    datas = [b.callback_data for b in keyboard.inline_keyboard[0]]
    assert datas == ["gift|alice12345|embroidery|2026", "gift|alice12345|money|2026"]
    mock_gift.assert_called_once_with("alice12345", 2026)


async def test_gift_checked_for_next_year_birthday():
    """Для ДР в начале следующего года подарок проверяется за следующий год."""
    bot = make_bot()
    from app.scheduler import send_reminders

    p1, p2, p3 = patch_db([("alice12345", "02.01")])
    with p1, p2, p3 as mock_gift, patch("app.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 12, 26)
        await send_reminders(bot)

    mock_gift.assert_called_once_with("alice12345", 2027)


async def test_no_keyboard_when_gift_already_chosen():
    """Клавиатура не прикрепляется, если подарок уже выбран."""
    bot = make_bot()

    await _send_reminders(bot, [("alice12345", "21.03")], gift="embroidery")

    assert bot.send_message.call_args.kwargs.get("reply_markup") is None


async def test_pending_gift_messages_populated():
    """После отправки (chat_id, message_id) сохраняется в pending_gift_messages."""
    import app.scheduler as sched

    bot = make_bot(message_id=99)

    await _send_reminders(bot, [("alice12345", "21.03")], chats=(-100, -200))

    assert sched.pending_gift_messages["alice12345"] == [(-100, 99), (-200, 99)]


async def test_failed_count_on_send_error():
    """Счётчик failed увеличивается при ошибке отправки."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

    (sent, failed), _ = await _send_reminders(bot, [("alice12345", "21.03")])

    assert (sent, failed) == (0, 1)


async def test_retry_after_flood_limit():
    """При flood-лимите бот ждёт и отправляет повторно."""
    sent_msg = MagicMock(message_id=1)
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[
        TelegramRetryAfter(method=MagicMock(), message="flood", retry_after=3),
        sent_msg,
    ])

    with patch("app.scheduler.asyncio.sleep", AsyncMock()) as mock_sleep:
        (sent, failed), _ = await _send_reminders(bot, [("alice12345", "21.03")])

    assert (sent, failed) == (1, 0)
    mock_sleep.assert_called_once_with(4)


async def test_invalid_date_counted_as_failed():
    """Именинники с кривой датой идут в failed."""
    bot = make_bot()

    (sent, failed), _ = await _send_reminders(bot, [("alice12345", "not-a-date")], force=True)

    assert (sent, failed) == (0, 1)


async def test_target_chat_id_overrides_chats():
    """target_chat_id заменяет список чатов из БД."""
    bot = make_bot()

    await _send_reminders(bot, [("alice12345", "21.03")], chats=(-999,), force=True, target_chat_id=12345)

    assert bot.send_message.call_args.kwargs["chat_id"] == 12345


# --- ежедневная рассылка и досылка после рестарта ---

async def _run(func, now: datetime, last_run: str | None):
    with patch("app.scheduler.datetime") as mock_dt, \
         patch("app.scheduler.get_state", AsyncMock(return_value=last_run)), \
         patch("app.scheduler.set_state", AsyncMock()) as mock_set, \
         patch("app.scheduler.send_reminders", AsyncMock(return_value=(1, 0))) as mock_send:
        mock_dt.now.return_value = now
        await func(MagicMock())
    return mock_send, mock_set


async def test_daily_sends_and_remembers_day():
    from app.scheduler import daily_reminders
    send, set_state = await _run(daily_reminders, datetime(2026, 3, 21, 9, 0), "2026-03-20")
    send.assert_called_once()
    set_state.assert_called_once_with("last_reminders_day", "2026-03-21")


async def test_daily_skips_if_already_sent_today():
    from app.scheduler import daily_reminders
    send, _ = await _run(daily_reminders, datetime(2026, 3, 21, 9, 0), "2026-03-21")
    send.assert_not_called()


async def test_catch_up_after_restart_past_9():
    from app.scheduler import catch_up_missed_run
    send, _ = await _run(catch_up_missed_run, datetime(2026, 3, 21, 12, 0), "2026-03-20")
    send.assert_called_once()


async def test_catch_up_does_nothing_before_9():
    from app.scheduler import catch_up_missed_run
    send, _ = await _run(catch_up_missed_run, datetime(2026, 3, 21, 8, 0), "2026-03-20")
    send.assert_not_called()


async def test_catch_up_first_launch_does_not_duplicate():
    """Первый запуск новой версии после 9:00 не дублирует уже сделанную рассылку."""
    from app.scheduler import catch_up_missed_run
    send, set_state = await _run(catch_up_missed_run, datetime(2026, 3, 21, 12, 0), None)
    send.assert_not_called()
    set_state.assert_called_once_with("last_reminders_day", "2026-03-21")
