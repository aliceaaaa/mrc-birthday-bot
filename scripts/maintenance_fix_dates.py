import asyncio
import asyncpg
from db import init_db, DATABASE_URL
from core.utils import normalize_date_or_none, normalize_username_or_none

async def main():
    await init_db()
    
    users_fixed = 0
    bdays_fixed = 0
    
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=1)
    
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, tg_username FROM users")
        
        for r in rows:
            fixed = normalize_username_or_none(r["tg_username"])
            if fixed and fixed != r["tg_username"]:
                await con.execute("UPDATE users SET tg_username=$1 WHERE id=$2", fixed, r["id"])
                users_fixed += 1
                
        rows = await con.fetch("SELECT user_id, date FROM birthdays")
        
        for r in rows:
            fixed = normalize_date_or_none(r["date"])
            
            if fixed and fixed != r["date"]:
                await con.execute("UPDATE birthdays SET date=$1 WHERE user_id=$2", fixed, r["user_id"])
                bdays_fixed += 1
                
    print(f"users_fixed={users_fixed}")
    print(f"birthdays_fixed={bdays_fixed}")

if __name__ == "__main__":
    asyncio.run(main())
