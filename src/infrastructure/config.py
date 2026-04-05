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

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 5_242_880))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 3))

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440))
API_PORT = int(os.getenv("API_PORT", 8000))

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # TODO: вставить когда сделаю домен вида "https://yourdomain.com"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/telegram")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("Missing EMAIL_USER or EMAIL_PASSWORD in .env")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")