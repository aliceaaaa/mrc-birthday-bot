import aiosqlite
from core.utils import normalize_date_or_none, normalize_username_or_none

DB_NAME = "birthdays.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            tg_username TEXT UNIQUE,
            username TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            user_id INTEGER UNIQUE,
            date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            user_id INTEGER UNIQUE,
            choice TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY
        )
        """)
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tg ON users(tg_username)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_birthdays_user ON birthdays(user_id)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_user ON gifts(user_id)")
        await db.commit()
    await audit_and_fix_db()

async def save_birthday(tg_username: str, date_str: str):
    norm_user = normalize_username_or_none(tg_username)
    norm_date = normalize_date_or_none(date_str)
    
    if not norm_user or not norm_date:
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_username) VALUES (?)",
            (norm_user,)
        )
        
        cursor = await db.execute(
            "SELECT id FROM users WHERE tg_username = ?",
            (norm_user,)
        )
        
        row = await cursor.fetchone()
        
        if not row:
            return
        
        await db.execute(
            "INSERT OR REPLACE INTO birthdays (user_id, date) VALUES (?, ?)",
            (row[0], norm_date)
        )
        
        await db.commit()

async def get_birthdays():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT users.tg_username, birthdays.date
            FROM birthdays
            JOIN users ON users.id = birthdays.user_id
        """)
        
        return await cursor.fetchall()

async def save_gift_by_username(tg_username: str, choice: str):
    norm_user = normalize_username_or_none(tg_username)
    
    if not norm_user:
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id FROM users WHERE tg_username = ?",
            (norm_user,)
        )
        row = await cursor.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users (tg_username) VALUES (?)",
                (norm_user,)
            )
            cursor = await db.execute(
                "SELECT id FROM users WHERE tg_username = ?",
                (norm_user,)
            )
            row = await cursor.fetchone()
            if not row:
                return
            
        user_id = row[0]
        
        await db.execute(
            "INSERT OR REPLACE INTO gifts (user_id, choice) VALUES (?, ?)",
            (user_id, choice)
        )
        
        await db.commit()

async def get_gift_by_username(tg_username: str) -> str | None:
    norm_user = normalize_username_or_none(tg_username)
    
    if not norm_user:
        return None
    
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT g.choice
            FROM gifts g
            JOIN users u ON u.id = g.user_id
            WHERE u.tg_username = ?
        """, (norm_user,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def save_chat(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO chats (chat_id) VALUES (?)",
            (chat_id,)
        )
        await db.commit()

async def get_chats():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT chat_id FROM chats")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def audit_and_fix_db():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, tg_username FROM users")
        users = await cursor.fetchall()
        
        for uid, uname in users:
            fixed = normalize_username_or_none(uname)
            if fixed and fixed != uname:
                await db.execute("UPDATE users SET tg_username = ? WHERE id = ?", (fixed, uid))
       
        cursor = await db.execute("SELECT user_id, date FROM birthdays")
        bds = await cursor.fetchall()
        
        for uid, d in bds:
            fixed = normalize_date_or_none(d)
            if fixed and fixed != d:
                await db.execute("UPDATE birthdays SET date = ? WHERE user_id = ?", (fixed, uid))
        await db.commit()

async def get_birthdays_in_month(mm: int):
    m2 = f"{mm:02d}"
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT u.tg_username, b.date
            FROM birthdays b
            JOIN users u ON u.id = b.user_id
            WHERE substr(b.date, 4, 2) = ?
        """, (m2,))
        return await cursor.fetchall()