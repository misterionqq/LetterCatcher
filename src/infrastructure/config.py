import os
from dotenv import load_dotenv

load_dotenv()

# --- Client mode ---
# "telegram" — only Telegram bot (TELEGRAM_BOT_TOKEN required)
# "web"      — only REST API + WebSocket (no bot, no BOT_TOKEN needed)
# "all"      — both simultaneously (default)
CLIENT_MODE = os.getenv("CLIENT_MODE", "all")

# --- App mode ---
APP_MODE = os.getenv("APP_MODE", "personal")
ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", 0))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")  # fallback for personal+web mode

# --- IMAP ---
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app.db")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- AI ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

# --- Logging ---
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 5_242_880))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 3))

# --- JWT / API ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440))
API_PORT = int(os.getenv("API_PORT", 8000))

# --- SMTP (email verification / password reset) ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

# --- Firebase (FCM push) ---
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/telegram")

# --- Validation ---
if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("Missing EMAIL_USER or EMAIL_PASSWORD in .env")

_uses_telegram = CLIENT_MODE in ("telegram", "all")
if _uses_telegram and not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env (required when CLIENT_MODE=telegram or all)")