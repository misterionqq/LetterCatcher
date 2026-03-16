import os
from dotenv import load_dotenv

load_dotenv()

APP_MODE = os.getenv("APP_MODE", "personal")
ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", 0))

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app.db")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("Missing EMAIL_USER or EMAIL_PASSWORD in .env")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")