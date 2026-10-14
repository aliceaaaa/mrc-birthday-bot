import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env is not set")

# Кто может добавлять/удалять ДР и пользоваться служебными командами
ADMIN_USERNAMES = {"alisandrii", "firasakhapova"}
