import asyncio
from datetime import date
from db import init_db, get_birthdays

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
    rows = await get_birthdays()
    
    for username, date_str in rows:
        d, m = map(int, date_str.split("."))
        nb = next_birthday(d, m, today)
        delta = (nb - today).days
        
        if delta <= days_ahead:
            rows_out.append((delta, username or "", f"{d:02d}.{m:02d}", nb.isoformat()))
            
    rows_out.sort(key=lambda x: (x[0], x[1]))
    
    print("in_days\tusername\tDD.MM\tcalendar_date")
    
    for r in rows_out:
        at = f"@{r[1]}" if r[1] else ""
        print(f"{r[0]}\t{at}\t{r[2]}\t{r[3]}")

if __name__ == "__main__":
    asyncio.run(main())
