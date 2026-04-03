import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from src.infrastructure.config import (
    TELEGRAM_BOT_TOKEN, IMAP_SERVER, EMAIL_USER, EMAIL_PASSWORD,
    OPENROUTER_API_KEY, LLM_MODEL, LOG_DIR, LOG_FILE, LOG_MAX_BYTES,
    LOG_BACKUP_COUNT, API_PORT,
)
from src.infrastructure.database.setup import init_db, AsyncSessionLocal
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.repositories.cache_repository import SQLAlchemyCacheRepository
from src.infrastructure.imap_client import ImapEmailRepository
from src.infrastructure.openrouter_client import OpenRouterAnalyzer
from src.use_cases.manage_users import ManageUsersUseCase
from src.use_cases.mail_scanner import MailScanner
from src.presentation.telegram.handlers import router as tg_router
from src.presentation.api.app import create_app
from src.presentation.api.dependencies import set_user_use_case

os.makedirs(LOG_DIR, exist_ok=True)
_log_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_console = logging.StreamHandler()
_console.setFormatter(_log_fmt)
_root.addHandler(_console)
_file = RotatingFileHandler(
    os.path.join(LOG_DIR, LOG_FILE),
    maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
)
_file.setFormatter(_log_fmt)
_root.addHandler(_file)


async def main():
    logging.info("Инициализация базы данных...")
    await init_db()

    user_repo = SQLAlchemyUserRepository(session_factory=AsyncSessionLocal)
    cache_repo = SQLAlchemyCacheRepository(session_factory=AsyncSessionLocal)
    email_repo = ImapEmailRepository(
        imap_server=IMAP_SERVER,
        email_user=EMAIL_USER,
        email_password=EMAIL_PASSWORD,
    )
    ai_analyzer = OpenRouterAnalyzer(api_key=OPENROUTER_API_KEY, model=LLM_MODEL)

    user_use_case = ManageUsersUseCase(user_repo=user_repo, cache_repo=cache_repo)

    # --- Telegram bot ---
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(tg_router)

    # --- REST API ---
    fastapi_app = create_app()
    set_user_use_case(user_use_case)

    api_config = uvicorn.Config(
        fastapi_app, host="0.0.0.0", port=API_PORT,
        log_level="info", access_log=False,
    )
    api_server = uvicorn.Server(api_config)

    # --- Mail scanner ---
    scanner = MailScanner(
        email_repo=email_repo, user_repo=user_repo,
        bot=bot, ai_analyzer=ai_analyzer, cache_repo=cache_repo,
    )
    scanner_task = asyncio.create_task(scanner.start_polling(interval_seconds=30))

    logging.info(f"LetterCatcher запущен! Telegram бот + API на порту {API_PORT}")

    try:
        await asyncio.gather(
            dp.start_polling(bot, user_use_case=user_use_case),
            api_server.serve(),
        )
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
