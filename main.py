import asyncio
import logging
import os
import ssl
from logging.handlers import RotatingFileHandler

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

import uvicorn

from src.infrastructure.config import (
    IMAP_SERVER, EMAIL_USER, EMAIL_PASSWORD,
    OPENROUTER_API_KEY, LLM_MODEL, LOG_DIR, LOG_FILE, LOG_MAX_BYTES,
    LOG_BACKUP_COUNT, API_PORT, WEBHOOK_URL, WEBHOOK_PATH,
    CLIENT_MODE, TELEGRAM_BOT_TOKEN,
    SMTP_SERVER, SMTP_PORT,
)
from src.infrastructure.database.setup import init_db, AsyncSessionLocal
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.repositories.cache_repository import SQLAlchemyCacheRepository
from src.infrastructure.repositories.token_repository import SQLAlchemyTokenRepository
from src.infrastructure.smtp_service import SmtpEmailSender
from src.infrastructure.imap_client import ImapEmailRepository
from src.infrastructure.openrouter_client import OpenRouterAnalyzer
from src.use_cases.manage_users import ManageUsersUseCase
from src.use_cases.mail_scanner import MailScanner
from src.presentation.api.app import create_app
from src.presentation.api.dependencies import set_user_use_case, set_scanner

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

_uses_telegram = CLIENT_MODE in ("telegram", "all")


async def main():
    logging.info("Инициализация базы данных...")
    await init_db()

    user_repo = SQLAlchemyUserRepository(session_factory=AsyncSessionLocal)
    cache_repo = SQLAlchemyCacheRepository(session_factory=AsyncSessionLocal)
    token_repo = SQLAlchemyTokenRepository(session_factory=AsyncSessionLocal)
    email_sender = SmtpEmailSender(
        smtp_server=SMTP_SERVER, smtp_port=SMTP_PORT,
        username=EMAIL_USER, password=EMAIL_PASSWORD,
    )
    email_repo = ImapEmailRepository(
        imap_server=IMAP_SERVER,
        email_user=EMAIL_USER,
        email_password=EMAIL_PASSWORD,
    )
    ai_analyzer = OpenRouterAnalyzer(api_key=OPENROUTER_API_KEY, model=LLM_MODEL)
    user_use_case = ManageUsersUseCase(
        user_repo=user_repo, cache_repo=cache_repo,
        token_repo=token_repo, email_sender=email_sender,
    )

    # --- Telegram bot (optional) ---
    bot = None
    dp = None
    if _uses_telegram:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from src.presentation.telegram.handlers import router as tg_router

        bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        dp = Dispatcher()
        dp.include_router(tg_router)

    # --- REST API ---
    fastapi_app = create_app()
    set_user_use_case(user_use_case)

    # --- Mail scanner ---
    scanner = MailScanner(
        email_repo=email_repo,
        user_repo=user_repo,
        ai_analyzer=ai_analyzer,
        cache_repo=cache_repo,
        bot=bot,
    )
    set_scanner(scanner)
    scanner_task = asyncio.create_task(scanner.start_polling(interval_seconds=30))

    api_config = uvicorn.Config(
        fastapi_app, host="0.0.0.0", port=API_PORT,
        log_level="info", access_log=False,
    )
    api_server = uvicorn.Server(api_config)

    use_webhook = _uses_telegram and bool(WEBHOOK_URL)

    if use_webhook:
        from aiogram.types import Update

        webhook_full = f"{WEBHOOK_URL}{WEBHOOK_PATH}"

        @fastapi_app.post(WEBHOOK_PATH)
        async def telegram_webhook(update: dict):
            telegram_update = Update.model_validate(update, context={"bot": bot})
            await dp.feed_update(bot=bot, update=telegram_update, user_use_case=user_use_case)

        @fastapi_app.on_event("startup")
        async def on_startup():
            await bot.set_webhook(webhook_full, drop_pending_updates=True)
            logging.info(f"Telegram webhook установлен: {webhook_full}")

        @fastapi_app.on_event("shutdown")
        async def on_shutdown():
            await bot.delete_webhook()

        logging.info(f"LetterCatcher запущен! Режим: {CLIENT_MODE} (webhook), API порт: {API_PORT}")

        try:
            await api_server.serve()
        finally:
            await _shutdown(scanner, scanner_task, email_repo, bot)

    elif _uses_telegram:
        logging.info(f"LetterCatcher запущен! Режим: {CLIENT_MODE} (polling), API порт: {API_PORT}")

        try:
            await asyncio.gather(
                dp.start_polling(bot, user_use_case=user_use_case),
                api_server.serve(),
            )
        finally:
            await _shutdown(scanner, scanner_task, email_repo, bot)

    else:
        logging.info(f"LetterCatcher запущен! Режим: {CLIENT_MODE} (web only), API порт: {API_PORT}")

        try:
            await api_server.serve()
        finally:
            await _shutdown(scanner, scanner_task, email_repo, bot=None)


async def _shutdown(scanner, scanner_task, email_repo, bot):
    logging.info("Завершение работы...")
    scanner.stop()
    try:
        await scanner_task
    except asyncio.CancelledError:
        pass
    await email_repo.disconnect()
    if bot:
        await bot.session.close()
    logging.info("Сервер остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Программа остановлена.")
