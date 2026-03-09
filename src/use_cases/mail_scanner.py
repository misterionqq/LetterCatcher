import asyncio
import logging
from aiogram import Bot
import html

from src.core.interfaces import IEmailRepository, IUserRepository
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID

class MailScanner:
    def __init__(self, email_repo: IEmailRepository, user_repo: IUserRepository, bot: Bot):
        self.email_repo = email_repo
        self.user_repo = user_repo
        self.bot = bot
        self.is_running = False

    async def start_polling(self, interval_seconds: int = 30):
        self.is_running = True
        logging.info("Служба мониторинга почты запущена.")
        
        while self.is_running:
            try:
                await self._check_mail_iteration()
            except Exception as e:
                logging.error(f"Ошибка при проверке почты: {e}")
            
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self.is_running = False

    async def _check_mail_iteration(self):
        emails = await self.email_repo.get_unread_emails(limit=5)
        if not emails:
            return

        logging.info(f"Найдено {len(emails)} новых писем. Начинаем анализ...")

        for email in emails:
            target_tg_id = None
            user_profile = None

            if APP_MODE == "personal":
                target_tg_id = ADMIN_TG_ID
                user_profile = await self.user_repo.get_by_telegram_id(target_tg_id)
            else:
                if email.recipient_email:
                    user_profile = await self.user_repo.get_by_email(email.recipient_email)
                    if user_profile:
                        target_tg_id = user_profile.telegram_id

            if not target_tg_id or not user_profile:
                logging.warning(f"Пропущено письмо: не найден адресат в БД (Email: {email.recipient_email})")
                continue

            is_important = False
            triggered_word = None

            search_text = (email.subject + " " + email.body).lower()
            
            if not user_profile.keywords:
                is_important = True 
            else:
                for kw in user_profile.keywords:
                    if kw.word in search_text:
                        if kw.is_stop_word:
                            is_important = False
                            break
                        else:
                            is_important = True
                            triggered_word = kw.word

            if is_important:
                # Экранируем спецсимволы (<, >, &), чтобы Telegram не принял их за HTML-теги
                safe_sender = html.escape(email.sender)
                safe_subject = html.escape(email.subject)
                safe_body = html.escape(email.body[:300]) # Взяли 300 символов для превью

                msg_text = (
                    f"🔔 <b>Новое важное письмо!</b>\n\n"
                    f"<b>От:</b> {safe_sender}\n"
                    f"<b>Тема:</b> {safe_subject}\n\n"
                    f"<i>{safe_body}...</i>\n"
                )
                if triggered_word:
                    msg_text += f"\n🎯 Сработало слово: <code>{triggered_word}</code>"

                try:
                    await self.bot.send_message(chat_id=target_tg_id, text=msg_text)
                    logging.info(f"Уведомление отправлено пользователю {target_tg_id}")
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение в TG: {e}")