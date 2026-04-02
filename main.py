import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from src.infrastructure.config import (
    TELEGRAM_BOT_TOKEN, IMAP_SERVER, EMAIL_USER, EMAIL_PASSWORD,
    OPENROUTER_API_KEY, LLM_MODEL, LOG_DIR, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT
)
from src.infrastructure.database.setup import init_db, AsyncSessionLocal
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.imap_client import ImapEmailRepository
from src.use_cases.manage_users import ManageUsersUseCase
from src.use_cases.mail_scanner import MailScanner
from src.presentation.telegram.handlers import router
from src.infrastructure.openrouter_client import OpenRouterAnalyzer
from src.infrastructure.repositories.cache_repository import SQLAlchemyCacheRepository

os.makedirs(LOG_DIR, exist_ok=True)
_log_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_console = logging.StreamHandler()
_console.setFormatter(_log_fmt)
_root.addHandler(_console)
_file = RotatingFileHandler(
    os.path.join(LOG_DIR, LOG_FILE),
    maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
)
_file.setFormatter(_log_fmt)
_root.addHandler(_file)

async def main():
    logging.info("Инициализация базы данных...")
    await init_db()

    user_repo = SQLAlchemyUserRepository(session_factory=AsyncSessionLocal)
    email_repo = ImapEmailRepository(
        imap_server=IMAP_SERVER,
        email_user=EMAIL_USER,
        email_password=EMAIL_PASSWORD
    )
    
    ai_analyzer = OpenRouterAnalyzer(api_key=OPENROUTER_API_KEY, model=LLM_MODEL)

    cache_repo = SQLAlchemyCacheRepository(session_factory=AsyncSessionLocal)

    user_use_case = ManageUsersUseCase(user_repo=user_repo, cache_repo=cache_repo)

    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)

    scanner = MailScanner(email_repo=email_repo, user_repo=user_repo, bot=bot, ai_analyzer=ai_analyzer, cache_repo=cache_repo)

    scanner_task = asyncio.create_task(scanner.start_polling(interval_seconds=30))

    logging.info("LetterCatcher Бот запущен! Нажмите Ctrl+C для остановки.")

    try:
        await dp.start_polling(bot, user_use_case=user_use_case)
    finally:
        logging.info("Завершение работы...")
        scanner.stop()
        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
        await email_repo.disconnect()
        await bot.session.close()
        logging.info("Бот остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Программа остановлена.")
        