import asyncio
from src.infrastructure.database.setup import init_db, AsyncSessionLocal
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from src.use_cases.manage_users import ManageUsersUseCase

async def main():
    print("--- Инициализация БД ---")
    await init_db()  # Создаст файл app.db и таблицы
    print("БД успешно инициализирована.")

    # Собираем зависимости
    user_repo = SQLAlchemyUserRepository(session_factory=AsyncSessionLocal)
    user_use_case = ManageUsersUseCase(user_repo=user_repo)

    test_tg_id = 123456789
    test_email = "student@edu.hse.ru"

    print("\n1. Регистрация пользователя...")
    user = await user_use_case.register_or_update_user(tg_id=test_tg_id, email=test_email)
    print(f"Пользователь создан: ID {user.telegram_id}, Email: {user.email}, Чувствительность: {user.ai_sensitivity}")

    print("\n2. Добавление ключевых слов (триггеров)...")
    await user_use_case.add_trigger_word(tg_id=test_tg_id, word="запись")
    await user_use_case.add_trigger_word(tg_id=test_tg_id, word="раздача")
    print("Слова 'запись' и 'раздача' добавлены.")

    print("\n3. Запрос профиля из БД...")
    profile = await user_use_case.get_user_profile(tg_id=test_tg_id)
    print(f"Профиль загружен. Email: {profile.email}")
    print("Его ключевые слова:")
    for kw in profile.keywords:
        tipo = "Стоп-слово" if kw.is_stop_word else "Триггер"
        print(f" - {kw.word} ({tipo})")

if __name__ == "__main__":
    # Запуск асинхронного приложения
    asyncio.run(main())