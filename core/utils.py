import re
from calendar import monthrange
from datetime import date, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Tbilisi")
except Exception:
    TZ = timezone(timedelta(hours=4), name="Asia/Tbilisi")


def normalize_date_or_none(s: str) -> str | None:
    if not isinstance(s, str):
        return None

    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\s*", s)

    if not m:
        return None

    d = int(m.group(1))
    mo = int(m.group(2))
    if not 1 <= mo <= 12:
        return None
    # 2000 — високосный год, поэтому 29.02 считается корректной датой
    if not 1 <= d <= monthrange(2000, mo)[1]:
        return None

    return f"{d:02d}.{mo:02d}"


def normalize_username_or_none(s: str | None) -> str | None:
    if not s:
        return None

    u = s.lstrip("@").strip()

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", u):
        return None

    return u.lower()


def birthday_in_year(day: int, month: int, year: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:
        # 29.02 в невисокосный год отмечаем 28.02
        if month == 2 and day == 29:
            return date(year, 2, 28)
        raise


def next_birthday(date_str: str, today: date) -> date | None:
    """Ближайший ДР (сегодня или позже) для даты вида DD.MM, None если дата кривая."""
    try:
        day, month = map(int, date_str.split("."))
        b = birthday_in_year(day, month, today.year)
        if b < today:
            b = birthday_in_year(day, month, today.year + 1)
        return b
    except (ValueError, AttributeError):
        return None


def gift_year(date_str: str, today: date) -> int:
    """К какому году относится ДР, подарок к которому выбирают сегодня.

    Кнопки выбора появляются не раньше чем за 7 дней до ДР, поэтому это
    последний ДР, который наступает не позже чем через 7 дней.
    """
    try:
        day, month = map(int, date_str.split("."))
        limit = today + timedelta(days=7)
        for y in (today.year + 1, today.year, today.year - 1):
            if birthday_in_year(day, month, y) <= limit:
                return y
    except (ValueError, AttributeError):
        pass
    return today.year


def days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"
