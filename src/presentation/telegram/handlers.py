from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.use_cases.manage_users import ManageUsersUseCase
from src.presentation.telegram.states import UserSettingsStates
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID

router = Router()

async def check_access(message: Message) -> bool:
    if APP_MODE == "personal" and message.from_user.id != ADMIN_TG_ID:
        await message.answer("⛔️ Бот работает в приватном режиме. Доступ запрещен.")
        return False
    return True

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    if not await check_access(message): return

    user = await user_use_case.register_or_update_user(tg_id=message.from_user.id)

    if APP_MODE == "centralized" and not user.email:
        await message.answer(
            "👋 Привет! Я — <b>LetterCatcher</b>.\n\n"
            "Для работы в корпоративном режиме укажите ваш рабочий email:",
            parse_mode="HTML"
        )
        await state.set_state(UserSettingsStates.waiting_for_email)
        return

    await _send_welcome(message)

async def _send_welcome(message: Message):
    if APP_MODE == "centralized":
        commands = (
            "👤 /profile - Мои настройки и ключевые слова\n"
            "📧 /email - Изменить привязанную почту\n"
            "🔕 /dnd - Не беспокоить (вкл/выкл)\n"
            "➕ /add - Добавить ключевое слово (триггер)\n"
            "➖ /remove - Удалить слово (например: /remove раздача)"
        )
    else:
        commands = (
            "👤 /profile - Мои настройки и ключевые слова\n"
            "🔕 /dnd - Не беспокоить (вкл/выкл)\n"
            "➕ /add - Добавить ключевое слово (триггер)\n"
            "➖ /remove - Удалить слово (например: /remove раздача)"
        )
    welcome_text = (
        "👋 Привет! Я — <b>LetterCatcher</b>.\n\n"
        "Я слежу за вашей почтой и присылаю уведомления только о <b>важных</b> событиях.\n\n"
        f"Доступные команды:\n{commands}"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(UserSettingsStates.waiting_for_email)
async def process_email_registration(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    email_input = message.text.strip().lower()
    await user_use_case.set_email(tg_id=message.from_user.id, email=email_input)
    await message.answer(f"📧 Email <b>{email_input}</b> привязан к вашему профилю.", parse_mode="HTML")
    await state.clear()
    await _send_welcome(message)

@router.message(Command("profile"))
async def cmd_profile(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message): return

    user = await user_use_case.get_user_profile(message.from_user.id)
    if not user:
        await message.answer("Сначала нажмите /start")
        return

    text = f"⚙️ <b>Ваш профиль:</b>\n"
    text += f"ID: <code>{user.telegram_id}</code>\n"
    text += f"Email: <b>{user.email or 'не привязан'}</b>\n"
    text += f"Чувствительность AI: <b>{user.ai_sensitivity}</b>\n"
    text += f"Не беспокоить: <b>{'включен 🔕' if user.is_dnd else 'выключен'}</b>\n\n"

    if not user.keywords:
        text += "<i>У вас пока нет ключевых слов для отслеживания. Нажмите /add чтобы добавить.</i>"
    else:
        text += "🎯 <b>Ключевые слова:</b>\n"
        for kw in user.keywords:
            text += f" • {kw.word}\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("email"))
async def cmd_email(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message): return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите email. Пример: <code>/email user@mail.ru</code>", parse_mode="HTML")
        return

    email = parts[1].strip().lower()
    await user_use_case.set_email(tg_id=message.from_user.id, email=email)
    await message.answer(f"📧 Email <b>{email}</b> привязан к вашему профилю.", parse_mode="HTML")

@router.message(Command("dnd"))
async def cmd_dnd(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message): return

    new_state = await user_use_case.toggle_dnd(tg_id=message.from_user.id)
    if new_state:
        await message.answer("🔕 Режим «Не беспокоить» <b>включен</b>. Уведомления приостановлены.", parse_mode="HTML")
    else:
        await message.answer("🔔 Режим «Не беспокоить» <b>выключен</b>. Уведомления возобновлены.", parse_mode="HTML")

@router.message(Command("add"))
async def cmd_add_keyword(message: Message, state: FSMContext):
    if not await check_access(message): return
    
    await message.answer("✏️ Напишите ключевое слово или фразу, которую нужно отслеживать (например: <i>запись на курс</i>):", parse_mode="HTML")
    await state.set_state(UserSettingsStates.waiting_for_keyword)

@router.message(UserSettingsStates.waiting_for_keyword)
async def process_keyword(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    word = message.text.strip().lower()
    
    await user_use_case.add_trigger_word(tg_id=message.from_user.id, word=word)
    await message.answer(f"✅ Слово <b>'{word}'</b> успешно добавлено в ваш список!", parse_mode="HTML")
    
    await state.clear()

@router.message(Command("remove"))
async def cmd_remove_keyword(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message): return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите слово для удаления. Пример: <code>/remove стипендия</code>", parse_mode="HTML")
        return
        
    word_to_remove = parts[1].strip().lower()
    
    await user_use_case.user_repo.remove_keyword(tg_id=message.from_user.id, word=word_to_remove)
    await message.answer(f"🗑 Слово <b>'{word_to_remove}'</b> удалено (если оно было в списке).", parse_mode="HTML")