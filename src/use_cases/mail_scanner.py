import asyncio
import hashlib
import logging
import re
from typing import Optional
from aiogram import Bot
import html

from src.core.entities import PendingNotification
from src.core.interfaces import IEmailRepository, IUserRepository, IAIAnalyzer, ICacheRepository
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID


class MailScanner:
    def __init__(self, email_repo: IEmailRepository, user_repo: IUserRepository, bot: Bot, ai_analyzer: IAIAnalyzer, cache_repo: ICacheRepository):
        self.email_repo = email_repo
        self.user_repo = user_repo
        self.bot = bot
        self.ai_analyzer = ai_analyzer
        self.cache_repo = cache_repo
        self.is_running = False
        self._stop_event = asyncio.Event()

    async def start_polling(self, interval_seconds: int = 30):
        self.is_running = True
        self._stop_event.clear()
        logging.info("Служба мониторинга почты запущена.")

        while self.is_running:
            try:
                await self._check_mail_iteration()
            except Exception as e:
                logging.error(f"Ошибка при проверке почты: {e}")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                break
            except asyncio.TimeoutError:
                continue

    def stop(self):
        self.is_running = False
        self._stop_event.set()

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

            if await self.user_repo.is_email_processed(target_tg_id, email.uid):
                logging.info(f"Письмо '{email.subject}' (UID: {email.uid}) уже обработано для пользователя {target_tg_id}.")
                continue

            is_important = False
            triggered_word = None
            ai_reason = ""

            search_text = (email.subject + " " + email.body).lower()

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
                await self.user_repo.mark_email_processed(
                    target_tg_id, email.uid,
                    sender=email.sender, subject=email.subject, is_important=False
                )
                continue

            sensitivity = user_profile.ai_sensitivity

            if sensitivity == "low":
                is_important = has_trigger
                if has_trigger:
                    logging.info(f"Триггер '{triggered_word}' сработал (Режим LOW, без AI). Письмо важное.")

            elif sensitivity == "medium":
                if has_trigger:
                    logging.info(f"Триггер '{triggered_word}' сработал (Режим MEDIUM). Передаем в AI...")
                    ai_result = await self._analyze_with_cache(email.subject, email.body)
                    is_important = ai_result["is_important"]
                    ai_reason = ai_result["reason"]
                else:
                    is_important = False

            elif sensitivity == "high":
                logging.info(f"Режим HIGH. Передаем письмо '{email.subject}' в AI...")
                ai_result = await self._analyze_with_cache(email.subject, email.body)
                is_important = ai_result["is_important"]
                ai_reason = ai_result["reason"]

            if is_important:
                action_url = self._extract_action_url(email.body)

                if user_profile.is_dnd:
                    logging.info(f"Письмо '{email.subject}' важное, но пользователь {target_tg_id} в DND. Сохраняем в отложенные.")
                    notification = PendingNotification(
                        user_id=target_tg_id,
                        email_uid=email.uid,
                        sender=email.sender,
                        subject=email.subject,
                        body_snippet=email.body[:250],
                        ai_reason=ai_reason,
                        triggered_word=triggered_word,
                        action_url=action_url,
                    )
                    await self.user_repo.add_pending_notification(notification)
                else:
                    msg_text = _format_notification(
                        sender=email.sender, subject=email.subject,
                        body_snippet=email.body[:250], ai_reason=ai_reason,
                        triggered_word=triggered_word, action_url=action_url,
                    )
                    for attempt in range(2):
                        try:
                            await self.bot.send_message(
                                chat_id=target_tg_id, text=msg_text,
                                parse_mode="HTML", disable_web_page_preview=True
                            )
                            logging.info(f"Уведомление отправлено пользователю {target_tg_id}")
                            break
                        except Exception as e:
                            logging.error(f"Не удалось отправить сообщение в TG (попытка {attempt + 1}): {e}")
                            if attempt == 0:
                                await asyncio.sleep(5)

            await self.user_repo.mark_email_processed(
                target_tg_id, email.uid,
                sender=email.sender, subject=email.subject, is_important=is_important
            )

    def _extract_action_url(self, body: str) -> Optional[str]:
        _NOISE = ("unsubscribe", "track", "pixel", "open.php", "click.php", "beacon")
        for match in re.finditer(r'https?://[^\s<>"\'\]]+', body):
            url = match.group(0).rstrip(".,;)")
            if len(url) <= 200 and not any(n in url.lower() for n in _NOISE):
                return url
        return None

    async def _analyze_with_cache(self, subject: str, body: str) -> dict:
        text_hash = hashlib.md5(body.encode()).hexdigest()
        cached = await self.cache_repo.get_cached_result(text_hash)
        if cached:
            logging.info(f"Результат AI взят из кэша (hash: {text_hash[:8]}...)")
            return cached
        ai_result = await self.ai_analyzer.analyze_urgency(subject, body)
        await self.cache_repo.save_cached_result(text_hash, ai_result["is_important"], ai_result["reason"])
        return ai_result


def _format_notification(sender: str, subject: str, body_snippet: str,
                         ai_reason: str, triggered_word: str = None,
                         action_url: str = None, pending: bool = False) -> str:
    safe_sender = html.escape(sender)
    safe_subject = html.escape(subject)
    safe_body = html.escape(body_snippet)

    prefix = "📩 <b>ОТЛОЖЕННОЕ УВЕДОМЛЕНИЕ</b>" if pending else "🔴 <b>ВАЖНОЕ ПИСЬМО!</b>"

    msg = (
        f"{prefix}\n\n"
        f"<b>От:</b> {safe_sender}\n"
        f"<b>Тема:</b> {safe_subject}\n\n"
        f"<i>{safe_body}...</i>\n\n"
        f"🤖 <b>Вывод AI:</b> {html.escape(ai_reason)}"
    )

    if triggered_word:
        msg += f"\n🎯 Триггер: <code>{triggered_word}</code>"

    if action_url:
        msg += f'\n🔗 <b>Ссылка:</b> <a href="{action_url}">Перейти</a>'

    return msg
