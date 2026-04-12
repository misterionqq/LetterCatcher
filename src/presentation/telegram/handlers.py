import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.use_cases.manage_users import ManageUsersUseCase
from src.use_cases.mail_scanner import _format_notification
from src.presentation.telegram.states import UserSettingsStates
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID, EMAIL_USER

router = Router()

_SENSITIVITY_LABELS = {
    "low":    "🔈 Только суперважные",
    "medium": "⚖️ Сбалансированный",
    "high":   "📣 Все подряд",
}


async def check_access(message: Message) -> bool:
    if APP_MODE == "personal" and message.from_user.id != ADMIN_TG_ID:
        await message.answer("⛔️ Бот работает в приватном режиме. Доступ запрещен.")
        return False
    return True


async def _get_user(tg_id: int, uc: ManageUsersUseCase, message: Message):
    """Resolve telegram_id to User entity. Sends error and returns None if not found."""
    user = await uc.get_user_profile_by_tg_id(tg_id)
    if not user:
        await message.answer("Сначала нажмите /start")
    return user


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await user_use_case.register_telegram_user(tg_id=message.from_user.id)

    if APP_MODE == "centralized" and not user.email:
        await message.answer(
            "👋 Привет! Я — <b>LetterCatcher</b>.\n\n"
            "Для работы в корпоративном режиме укажите ваш рабочий email:",
            parse_mode="HTML",
        )
        await state.set_state(UserSettingsStates.waiting_for_email)
        return

    await _send_welcome(message)


async def _send_welcome(message: Message):
    common_commands = (
        "👤 /profile — Мои настройки и ключевые слова\n"
        "⚙️ /sensitivity — Настройка чувствительности\n"
        "🔕 /dnd — Не беспокоить (вкл/выкл)\n"
        "➕ /add — Добавить ключевое слово (триггер)\n"
        "🚫 /stop — Добавить стоп-слово\n"
        "➖ /remove — Удалить слово (например: /remove реклама)\n"
        "📜 /history — Последние обработанные письма\n"
        "📊 /stats — Статистика"
    )

    if APP_MODE == "centralized":
        commands = f"📧 /email — Изменить привязанную почту\n{common_commands}"
        forwarding_hint = (
            "\n\n📬 <b>Настройте автопересылку писем:</b>\n"
            f"Перенаправьте входящие письма с корпоративной почты на:\n"
            f"<code>{EMAIL_USER}</code>\n"
            "<i>Настройки почты → Фильтры и пересылка → Переслать копии на адрес</i>"
        )
    else:
        commands = common_commands
        forwarding_hint = ""

    welcome_text = (
        "👋 Привет! Я — <b>LetterCatcher</b>.\n\n"
        "Я слежу за вашей почтой и присылаю уведомления только о <b>важных</b> событиях.\n\n"
        f"Доступные команды:\n{commands}"
        f"{forwarding_hint}"
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(UserSettingsStates.waiting_for_email)
async def process_email_registration(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    email_input = message.text.strip().lower()
    try:
        await user_use_case.set_email(user_id=user.id, email=email_input)
    except ValueError:
        await message.answer("❌ Неверный формат email. Попробуйте ещё раз:", parse_mode="HTML")
        return
    await message.answer(f"📧 Email <b>{email_input}</b> привязан к вашему профилю.", parse_mode="HTML")
    await state.clear()
    await _send_welcome(message)


@router.message(Command("profile"))
async def cmd_profile(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    sensitivity_label = _SENSITIVITY_LABELS.get(user.ai_sensitivity, user.ai_sensitivity)

    text = "⚙️ <b>Ваш профиль:</b>\n"
    text += f"ID: <code>{user.telegram_id}</code>\n"
    if APP_MODE == "centralized":
        text += f"Email: <b>{user.email or 'не привязан'}</b>\n"
    text += f"Чувствительность AI: <b>{sensitivity_label}</b>\n"
    text += f"Не беспокоить: <b>{'включен 🔕' if user.is_dnd else 'выключен'}</b>\n\n"

    triggers = [kw for kw in user.keywords if not kw.is_stop_word]
    stop_words = [kw for kw in user.keywords if kw.is_stop_word]

    if not triggers and not stop_words:
        text += "<i>У вас пока нет ключевых слов. Нажмите /add или /stop чтобы добавить.</i>"
    else:
        if triggers:
            text += "🎯 <b>Триггерные слова:</b>\n"
            for kw in triggers:
                text += f" • {kw.word}\n"
        if stop_words:
            text += "🚫 <b>Стоп-слова:</b>\n"
            for kw in stop_words:
                text += f" • {kw.word}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("sensitivity"))
async def cmd_sensitivity(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    current = user.ai_sensitivity if user else "medium"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == lvl else ''}{label}",
            callback_data=f"sensitivity_{lvl}",
        )]
        for lvl, label in _SENSITIVITY_LABELS.items()
    ])

    await message.answer(
        "⚙️ Выберите уровень чувствительности фильтров:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("sensitivity_"))
async def callback_sensitivity(call: CallbackQuery, user_use_case: ManageUsersUseCase):
    level = call.data.split("_", 1)[1]
    if level not in _SENSITIVITY_LABELS:
        await call.answer("Неверный уровень.")
        return

    user = await user_use_case.get_user_profile_by_tg_id(call.from_user.id)
    if not user:
        await call.answer("Сначала /start")
        return

    await user_use_case.set_sensitivity(user_id=user.id, level=level)
    label = _SENSITIVITY_LABELS[level]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if lvl == level else ''}{lbl}",
            callback_data=f"sensitivity_{lvl}",
        )]
        for lvl, lbl in _SENSITIVITY_LABELS.items()
    ])

    await call.message.edit_reply_markup(reply_markup=keyboard)
    await call.answer(f"Установлено: {label}")


@router.message(Command("email"))
async def cmd_email(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите email. Пример: <code>/email user@mail.ru</code>", parse_mode="HTML")
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    email = parts[1].strip().lower()
    try:
        await user_use_case.set_email(user_id=user.id, email=email)
    except ValueError:
        await message.answer("❌ Неверный формат email. Пример: <code>/email user@mail.ru</code>", parse_mode="HTML")
        return
    await message.answer(f"📧 Email <b>{email}</b> привязан к вашему профилю.", parse_mode="HTML")


@router.message(Command("dnd"))
async def cmd_dnd(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    new_state, pending = await user_use_case.toggle_dnd(user_id=user.id)
    if new_state:
        await message.answer("🔕 Режим «Не беспокоить» <b>включен</b>. Уведомления приостановлены.", parse_mode="HTML")
    else:
        if pending:
            await message.answer(
                f"🔔 Режим «Не беспокоить» <b>выключен</b>.\n"
                f"📩 Отправляю {len(pending)} отложенных уведомлений...",
                parse_mode="HTML",
            )
            for notif in pending:
                msg = _format_notification(
                    sender=notif.sender, subject=notif.subject,
                    body_snippet=notif.body_snippet, ai_reason=notif.ai_reason,
                    triggered_word=notif.triggered_word, action_url=notif.action_url,
                    pending=True,
                )
                await message.answer(msg, parse_mode="HTML", disable_web_page_preview=True)
                await asyncio.sleep(0.3)
        else:
            await message.answer("🔔 Режим «Не беспокоить» <b>выключен</b>. Уведомления возобновлены.", parse_mode="HTML")


@router.message(Command("add"))
async def cmd_add_keyword(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    await state.update_data(user_id=user.id)
    await message.answer(
        "✏️ Напишите ключевое слово или фразу (например: <i>дедлайн</i>):",
        parse_mode="HTML",
    )
    await state.set_state(UserSettingsStates.waiting_for_keyword)


@router.message(UserSettingsStates.waiting_for_keyword)
async def process_keyword(message: Message, state: FSMContext, user_use_case: ManageUsersUseCase):
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        await state.clear()
        return

    word = message.text.strip().lower()
    try:
        await user_use_case.add_trigger_word(user_id=user_id, word=word)
    except ValueError:
        await message.answer(f"⚠️ Слово <b>'{word}'</b> уже есть в вашем списке.", parse_mode="HTML")
        await state.clear()
        return

    await message.answer(f"✅ Слово <b>'{word}'</b> успешно добавлено!", parse_mode="HTML")
    await state.clear()


@router.message(Command("stop"))
async def cmd_stop_word(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Укажите стоп-слово. Пример: <code>/stop реклама</code>\n"
            "Письма с этим словом будут игнорироваться.",
            parse_mode="HTML",
        )
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    word = parts[1].strip().lower()
    try:
        await user_use_case.add_stop_word(user_id=user.id, word=word)
    except ValueError:
        await message.answer(f"⚠️ Стоп-слово <b>'{word}'</b> уже есть в списке.", parse_mode="HTML")
        return

    await message.answer(f"🚫 Стоп-слово <b>'{word}'</b> добавлено.", parse_mode="HTML")


@router.message(Command("remove"))
async def cmd_remove_keyword(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Укажите слово для удаления. Пример: <code>/remove стипендия</code>",
            parse_mode="HTML",
        )
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    word_to_remove = parts[1].strip().lower()
    await user_use_case.user_repo.remove_keyword(user_id=user.id, word=word_to_remove)
    await message.answer(f"🗑 Слово <b>'{word_to_remove}'</b> удалено (если оно было в списке).", parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    history = await user_use_case.get_email_history(user_id=user.id, limit=10)
    if not history:
        await message.answer("📜 История пуста — пока не обработано ни одного письма.")
        return

    text = "📜 <b>Последние обработанные письма:</b>\n\n"
    for item in history:
        icon = "🔴" if item["is_important"] else "⚪️"
        sender = item.get("sender") or "—"
        subject = item.get("subject") or "—"
        date = item["processed_at"].strftime("%d.%m %H:%M") if item.get("processed_at") else ""
        text += f"{icon} <b>{subject}</b>\n   От: {sender} | {date}\n\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message, user_use_case: ManageUsersUseCase):
    if not await check_access(message):
        return

    user = await _get_user(message.from_user.id, user_use_case, message)
    if not user:
        return

    stats = await user_use_case.get_stats(user_id=user.id)

    text = (
        "📊 <b>Статистика:</b>\n\n"
        f"📬 Всего обработано писем: <b>{stats['total_processed']}</b>\n"
        f"🔴 Из них важных: <b>{stats['important_count']}</b>\n"
        f"💾 Записей в AI-кэше: <b>{stats['cache_total']}</b>"
    )

    await message.answer(text, parse_mode="HTML")
