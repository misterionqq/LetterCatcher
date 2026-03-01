import os
from dotenv import load_dotenv

load_dotenv()

# 'personal' (1 bot = 1 user) | 'centralized' (1 bot = many users)
APP_MODE = os.getenv("APP_MODE", "personal")

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.yandex.ru")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app.db")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("Missing EMAIL_USER or EMAIL_PASSWORD in .env")