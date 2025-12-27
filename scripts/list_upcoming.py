import asyncio
from datetime import date
import aiosqlite
from db import DB_NAME, init_db

def next_birthday(day: int, month: int, today: date) -> date:
    try:
        d = date(today.year, month, day)
    except ValueError:
        if month == 2 and day == 29:
            d = date(today.year, 2, 28)
        else:
            raise
    if d < today:
        try:
            d = d.replace(year=today.year + 1)
        except ValueError:
            if month == 2 and day == 29:
                d = date(today.year + 1, 2, 28)
            else:
                raise
    return d

async def main(days_ahead: int = 30):
    await init_db()
    today = date.today()
    rows_out = []
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT u.tg_username, b.date
            FROM birthdays b
            JOIN users u ON u.id = b.user_id
            WHERE u.tg_username IS NOT NULL
        """)
        rows = await cursor.fetchall()
    for username, date_str in rows:
        d, m = map(int, date_str.split("."))
        nb = next_birthday(d, m, today)
        delta = (nb - today).days
        if delta <= days_ahead:
            rows_out.append((delta, username, f"{d:02d}.{m:02d}", nb.isoformat()))
    rows_out.sort(key=lambda x: (x[0], x[1] or ""))
    print("in_days\tusername\tDD.MM\tcalendar_date")
    for r in rows_out:
        print(f"{r[0]}\t@{r[1]}\t{r[2]}\t{r[3]}")

if __name__ == "__main__":
    asyncio.run(main())
