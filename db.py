import aiosqlite

DB_NAME = "birthdays.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            tg_username TEXT UNIQUE,
            username TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            user_id INTEGER,
            date TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            user_id INTEGER,
            choice TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY
        )
        """)
        await db.commit()

async def save_birthday(tg_username: str, date_str: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO users (tg_username)
            VALUES (?)
            """,
            (tg_username,)
        )

        cursor = await db.execute(
            "SELECT id FROM users WHERE tg_username = ?",
            (tg_username,)
        )
        row = await cursor.fetchone()
        if not row:
            return

        await db.execute(
            "INSERT OR REPLACE INTO birthdays (user_id, date) VALUES (?, ?)",
            (row[0], date_str)
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

async def save_gift(user_id: str, choice: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO gifts (user_id, choice) VALUES (?, ?)",
            (user_id, choice)
        )
        await db.commit()
        
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

async def get_gift(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT choice FROM gifts WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else "подарок ек выбран"