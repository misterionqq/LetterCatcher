import asyncio
import logging
from aiogram import Bot
import html

from src.core.interfaces import IEmailRepository, IUserRepository, IAIAnalyzer
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID

class MailScanner:
    def __init__(self, email_repo: IEmailRepository, user_repo: IUserRepository, bot: Bot, ai_analyzer: IAIAnalyzer):
        self.email_repo = email_repo
        self.user_repo = user_repo
        self.bot = bot
        self.ai_analyzer = ai_analyzer
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
            ai_reason = ""

            search_text = (email.subject + " " + email.body).lower()
            
            # Step 1: Static analysis (RegEx / Keywords)
            has_trigger = False
            is_stopped = False

            if user_profile.keywords:
                for kw in user_profile.keywords:
                    if kw.word in search_text:
                        if kw.is_stop_word:
                            is_stopped = True
                            break
                        else:
                            has_trigger = True
                            triggered_word = kw.word

            if is_stopped:
                logging.info(f"Письмо '{email.subject}' пропущено (сработало стоп-слово).")
                continue

            # Step 2: LLM
            sensitivity = user_profile.ai_sensitivity

            if sensitivity == "low":
                is_important = has_trigger
                if has_trigger:
                    logging.info(f"⚡️ Триггер '{triggered_word}' сработал (Режим LOW, без AI). Письмо важное.")
            
            elif sensitivity == "medium":
                if has_trigger:
                    logging.info(f"⚡️ Триггер '{triggered_word}' сработал (Режим MEDIUM). Передаем в AI...")
                    ai_result = await self.ai_analyzer.analyze_urgency(email.subject, email.body)
                    is_important = ai_result["is_important"]
                    ai_reason = ai_result["reason"]
                else:
                    logging.info(f"Письмо '{email.subject}' пропущено (нет триггерных слов).")
                    is_important = False
            
            elif sensitivity == "high":
                logging.info(f"⚡️ Режим HIGH. Передаем письмо '{email.subject}' в AI без проверки триггеров...")
                ai_result = await self.ai_analyzer.analyze_urgency(email.subject, email.body)
                is_important = ai_result["is_important"]
                ai_reason = ai_result["reason"]

            if is_important:
                safe_sender = html.escape(email.sender)
                safe_subject = html.escape(email.subject)
                safe_body = html.escape(email.body[:250])

                msg_text = (
                    f"🔴 <b>ВАЖНОЕ ПИСЬМО!</b>\n\n"
                    f"<b>От:</b> {safe_sender}\n"
                    f"<b>Тема:</b> {safe_subject}\n\n"
                    f"<i>{safe_body}...</i>\n\n"
                    f"🤖 <b>Вывод AI:</b> {html.escape(ai_reason)}"
                )
                
                if triggered_word:
                    msg_text += f"\n🎯 Триггер: <code>{triggered_word}</code>"

                try:
                    await self.bot.send_message(chat_id=target_tg_id, text=msg_text)
                    logging.info(f"Уведомление (AI) отправлено пользователю {target_tg_id}")
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение в TG: {e}")