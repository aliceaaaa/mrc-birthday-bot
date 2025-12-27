import asyncio
import aiosqlite
from db import DB_NAME, init_db
from core.utils import normalize_date_or_none, normalize_username_or_none

async def main():
    await init_db()
    users_fixed = 0
    bdays_fixed = 0
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, tg_username FROM users")
        users = await cursor.fetchall()
        for uid, uname in users:
            fixed = normalize_username_or_none(uname)
            if fixed and fixed != uname:
                await db.execute("UPDATE users SET tg_username = ? WHERE id = ?", (fixed, uid))
                users_fixed += 1
        cursor = await db.execute("SELECT user_id, date FROM birthdays")
        bds = await cursor.fetchall()
        for uid, d in bds:
            fixed = normalize_date_or_none(d)
            if fixed and fixed != d:
                await db.execute("UPDATE birthdays SET date = ? WHERE user_id = ?", (fixed, uid))
                bdays_fixed += 1
        await db.commit()
    print(f"users_fixed={users_fixed}")
    print(f"birthdays_fixed={bdays_fixed}")

if __name__ == "__main__":
    asyncio.run(main())
