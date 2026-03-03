import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from src.infrastructure.config import TELEGRAM_BOT_TOKEN
from src.infrastructure.database.setup import init_db, AsyncSessionLocal
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from src.use_cases.manage_users import ManageUsersUseCase
from src.presentation.telegram.handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

async def main():
    logging.info("Инициализация базы данных...")
    await init_db()

    user_repo = SQLAlchemyUserRepository(session_factory=AsyncSessionLocal)
    user_use_case = ManageUsersUseCase(user_repo=user_repo)

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()

    dp.include_router(router)

    logging.info("LetterCatcher Бот запущен! Нажмите Ctrl+C для остановки.")
    
    await dp.start_polling(bot, user_use_case=user_use_case)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")