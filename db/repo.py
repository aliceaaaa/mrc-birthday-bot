import os
import asyncpg
from core.utils import normalize_date_or_none, normalize_username_or_none


DATABASE_URL = os.environ.get("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, ssl=True)
    return _pool

async def init_db():
    pool = await _get_pool()
    async with pool.acquire() as con:
        await con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tg_username TEXT UNIQUE,
            username TEXT
        )
        """)
        await con.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            date TEXT
        )
        """)
        await con.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            choice TEXT
        )
        """)
        await con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id BIGINT PRIMARY KEY
        )
        """)
        await con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tg ON users(tg_username)")
        await con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_birthdays_user ON birthdays(user_id)")
        await con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_user ON gifts(user_id)")
    await audit_and_fix_db()


async def save_birthday(tg_username: str, date_str: str):
    norm_user = normalize_username_or_none(tg_username)
    norm_date = normalize_date_or_none(date_str)
    if not norm_user or not norm_date:
        return
    pool = await _get_pool()
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO users(tg_username) VALUES($1) ON CONFLICT (tg_username) DO NOTHING",
            norm_user,
        )
        row = await con.fetchrow("SELECT id FROM users WHERE tg_username=$1", norm_user)
        if not row:
            return
        await con.execute("""
            INSERT INTO birthdays(user_id, date) VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET date=EXCLUDED.date
        """, row["id"], norm_date)


async def get_birthdays():
    pool = await _get_pool()
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT u.tg_username, b.date
            FROM birthdays b
            JOIN users u ON u.id = b.user_id
        """)
        return [(r["tg_username"], r["date"]) for r in rows]


async def save_gift_by_username(tg_username: str, choice: str):
    norm_user = normalize_username_or_none(tg_username)
    if not norm_user:
        return
    pool = await _get_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT id FROM users WHERE tg_username=$1", norm_user)
        if not row:
            await con.execute("INSERT INTO users(tg_username) VALUES($1)", norm_user)
            row = await con.fetchrow("SELECT id FROM users WHERE tg_username=$1", norm_user)
            if not row:
                return
        await con.execute("""
            INSERT INTO gifts(user_id, choice) VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET choice=EXCLUDED.choice
        """, row["id"], choice)


async def get_gift_by_username(tg_username: str) -> str | None:
    norm_user = normalize_username_or_none(tg_username)
    if not norm_user:
        return None
    pool = await _get_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow("""
            SELECT g.choice
            FROM gifts g
            JOIN users u ON u.id = g.user_id
            WHERE u.tg_username=$1
        """, norm_user)
        return row["choice"] if row else None


async def save_chat(chat_id: int):
    pool = await _get_pool()
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO chats(chat_id) VALUES($1) ON CONFLICT (chat_id) DO NOTHING",
            chat_id,
        )


async def get_chats():
    pool = await _get_pool()
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT chat_id FROM chats")
        return [r["chat_id"] for r in rows]


async def audit_and_fix_db():
    pool = await _get_pool()
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, tg_username FROM users")
        for r in rows:
            fixed = normalize_username_or_none(r["tg_username"])
            if fixed and fixed != r["tg_username"]:
                await con.execute("UPDATE users SET tg_username=$1 WHERE id=$2", fixed, r["id"])
        rows = await con.fetch("SELECT user_id, date FROM birthdays")
        for r in rows:
            fixed = normalize_date_or_none(r["date"])
            if fixed and fixed != r["date"]:
                await con.execute("UPDATE birthdays SET date=$1 WHERE user_id=$2", fixed, r["user_id"])


async def get_birthdays_in_month(mm: int):
    m2 = f"{mm:02d}"
    pool = await _get_pool()
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT u.tg_username, b.date
            FROM birthdays b
            JOIN users u ON u.id = b.user_id
            WHERE SUBSTRING(b.date FROM 4 FOR 2) = $1
        """, m2)
        return [(r["tg_username"], r["date"]) for r in rows]


async def count_birthdays() -> int:
    pool = await _get_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT COUNT(*) AS n FROM birthdays")
        return int(row["n"]) if row else 0


async def get_birthday_by_username(tg_username: str) -> str | None:
    norm_user = normalize_username_or_none(tg_username)
    if not norm_user:
        return None
    pool = await _get_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow("""
            SELECT b.date
            FROM birthdays b
            JOIN users u ON u.id = b.user_id
            WHERE u.tg_username=$1
        """, norm_user)
        return row["date"] if row else None
