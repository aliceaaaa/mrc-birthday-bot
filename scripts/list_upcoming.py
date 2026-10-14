import asyncio
from datetime import datetime
from db import init_db, get_birthdays
from core.utils import TZ, next_birthday


async def main(days_ahead: int = 30):
    await init_db()

    today = datetime.now(TZ).date()
    rows_out = []
    rows = await get_birthdays()

    for username, date_str in rows:
        nb = next_birthday(date_str, today)
        if nb is None:
            continue
        delta = (nb - today).days

        if delta <= days_ahead:
            rows_out.append((delta, username or "", date_str, nb.isoformat()))

    rows_out.sort(key=lambda x: (x[0], x[1]))

    print("in_days\tusername\tDD.MM\tcalendar_date")

    for r in rows_out:
        at = f"@{r[1]}" if r[1] else ""
        print(f"{r[0]}\t{at}\t{r[2]}\t{r[3]}")

if __name__ == "__main__":
    asyncio.run(main())
