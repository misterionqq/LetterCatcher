import asyncio
import hashlib
import logging
import html

from src.core.entities import PendingNotification
from src.core.interfaces import IEmailRepository, IUserRepository, IAIAnalyzer, ICacheRepository
from src.infrastructure.config import APP_MODE, ADMIN_TG_ID, ADMIN_EMAIL

_ws_manager = None


def _get_ws_manager():
    global _ws_manager
    if _ws_manager is None:
        try:
            from src.presentation.api.ws_manager import ws_manager
            _ws_manager = ws_manager
        except ImportError:
            pass
    return _ws_manager


class MailScanner:
    def __init__(self, email_repo: IEmailRepository, user_repo: IUserRepository,
                 ai_analyzer: IAIAnalyzer, cache_repo: ICacheRepository,
                 bot=None):
        self.email_repo = email_repo
        self.user_repo = user_repo
        self.ai_analyzer = ai_analyzer
        self.cache_repo = cache_repo
        self.bot = bot  # Optional: None when CLIENT_MODE=web
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
            user_profile = None
            logging.info(f"Обработка: '{email.subject}' от {email.sender}, recipient={email.recipient_email}")

            if APP_MODE == "personal":
                if ADMIN_TG_ID:
                    user_profile = await self.user_repo.get_by_telegram_id(ADMIN_TG_ID)
                elif ADMIN_EMAIL:
                    user_profile = await self.user_repo.get_by_email(ADMIN_EMAIL)
            else:
                if email.recipient_email:
                    user_profile = await self.user_repo.get_by_email(email.recipient_email)

            if not user_profile:
                logging.warning(f"Пропущено письмо: не найден адресат (recipient={email.recipient_email})")
                continue

            if APP_MODE == "centralized" and not getattr(user_profile, 'email_verified', True):
                logging.warning(f"Пропущено письмо для user {user_profile.id}: email не верифицирован")
                continue

            target_user_id = user_profile.id

            if await self.user_repo.is_email_processed(target_user_id, email.uid):
                logging.info(f"Письмо '{email.subject}' (UID: {email.uid}) уже обработано.")
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
                logging.info(f"Письмо '{email.subject}' пропущено (стоп-слово).")
                await self.user_repo.mark_email_processed(
                    target_user_id, email.uid,
                    sender=email.sender, subject=email.subject, is_important=False,
                    email_date=email.date, body_full=email.body,
                    body_html=email.body_html, links=email.links,
                    attachments=email.attachments,
                )
                continue

            sensitivity = user_profile.ai_sensitivity

            if sensitivity == "low":
                is_important = has_trigger
                if has_trigger:
                    logging.info(f"Триггер '{triggered_word}' сработал (LOW, без AI).")

            elif sensitivity == "medium":
                if has_trigger:
                    logging.info(f"Триггер '{triggered_word}' сработал (MEDIUM). Передаём в AI...")
                    ai_result = await self._analyze_with_cache(email.subject, email.body)
                    is_important = ai_result["is_important"]
                    ai_reason = ai_result["reason"]
                else:
                    is_important = False

            elif sensitivity == "high":
                logging.info(f"Режим HIGH. Передаём '{email.subject}' в AI...")
                ai_result = await self._analyze_with_cache(email.subject, email.body)
                is_important = ai_result["is_important"]
                ai_reason = ai_result["reason"]

            action_url = email.links[0] if email.links else None

            if is_important:
                if user_profile.is_dnd:
                    logging.info(f"Письмо важное, но пользователь {target_user_id} в DND. Сохраняем.")
                    notification = PendingNotification(
                        user_id=target_user_id,
                        email_uid=email.uid,
                        sender=email.sender,
                        subject=email.subject,
                        body_snippet=email.body[:250],
                        body_full=email.body,
                        body_html=email.body_html,
                        links=email.links,
                        attachments=email.attachments,
                        ai_reason=ai_reason,
                        triggered_word=triggered_word,
                        action_url=action_url,
                    )
                    await self.user_repo.add_pending_notification(notification)
                else:
                    if self.bot and user_profile.telegram_id:
                        msg_text = _format_notification(
                            sender=email.sender, subject=email.subject,
                            body_snippet=email.body[:250], ai_reason=ai_reason,
                            triggered_word=triggered_word, action_url=action_url,
                        )
                        for attempt in range(2):
                            try:
                                await self.bot.send_message(
                                    chat_id=user_profile.telegram_id, text=msg_text,
                                    parse_mode="HTML", disable_web_page_preview=True,
                                )
                                logging.info(f"Telegram-уведомление отправлено пользователю {target_user_id}")
                                break
                            except Exception as e:
                                logging.error(f"Не удалось отправить TG (попытка {attempt + 1}): {e}")
                                if attempt == 0:
                                    await asyncio.sleep(5)

                    await self._send_push(target_user_id, email.sender, email.subject, email.uid)

            mgr = _get_ws_manager()
            if mgr and mgr.has_connections(target_user_id):
                await mgr.send_to_user(target_user_id, {
                    "type": "email_notification",
                    "email_uid": email.uid,
                    "sender": email.sender,
                    "subject": email.subject,
                    "date": email.date.isoformat(),
                    "is_important": is_important,
                    "body_snippet": email.body[:250],
                    "body_full": email.body,
                    "body_html": email.body_html,
                    "links": email.links,
                    "attachments": email.attachments,
                    "ai_reason": ai_reason,
                    "triggered_word": triggered_word,
                    "action_url": action_url,
                })

            await self.user_repo.mark_email_processed(
                target_user_id, email.uid,
                sender=email.sender, subject=email.subject, is_important=is_important,
                email_date=email.date, body_full=email.body,
                body_html=email.body_html, ai_reason=ai_reason,
                triggered_word=triggered_word, action_url=action_url,
                links=email.links, attachments=email.attachments,
            )

    async def _send_push(self, user_id: int, sender: str, subject: str, email_uid: str):
        try:
            from src.infrastructure.fcm_service import send_push
            tokens = await self.user_repo.get_device_tokens(user_id)
            if not tokens:
                return
            removed = await send_push(
                tokens,
                title=f"Важное письмо от {sender}",
                body=subject,
                data={"email_uid": email_uid},
            )
            if removed:
                await self.user_repo.remove_device_tokens(removed)
        except Exception as e:
            logging.error(f"FCM push error: {e}")

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
