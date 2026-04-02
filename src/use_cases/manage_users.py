import re
from typing import List, Optional

from src.core.entities import User, Keyword, PendingNotification
from src.core.interfaces import IUserRepository, ICacheRepository

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class ManageUsersUseCase:
    def __init__(self, user_repo: IUserRepository, cache_repo: ICacheRepository = None):
        self.user_repo = user_repo
        self.cache_repo = cache_repo

    async def register_or_update_user(self, tg_id: int, email: str = None) -> User:
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if not user:
            user = User(telegram_id=tg_id, email=email)
        else:
            if email:
                user.email = email

        await self.user_repo.save_user(user)
        return await self.user_repo.get_by_telegram_id(tg_id)

    async def add_trigger_word(self, tg_id: int, word: str):
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if user:
            for kw in user.keywords:
                if kw.word == word.lower():
                    raise ValueError("duplicate_keyword")
        await self.user_repo.add_keyword(tg_id, Keyword(word=word, is_stop_word=False))

    async def add_stop_word(self, tg_id: int, word: str):
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if user:
            for kw in user.keywords:
                if kw.word == word.lower():
                    if kw.is_stop_word:
                        raise ValueError("already_exists")
                    await self.user_repo.remove_keyword(tg_id, word)
                    break
        await self.user_repo.add_keyword(tg_id, Keyword(word=word, is_stop_word=True))

    async def get_user_profile(self, tg_id: int) -> Optional[User]:
        return await self.user_repo.get_by_telegram_id(tg_id)

    async def set_email(self, tg_id: int, email: str) -> None:
        if not _EMAIL_RE.match(email):
            raise ValueError("invalid_email")
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if user:
            user.email = email
            await self.user_repo.save_user(user)

    async def set_sensitivity(self, tg_id: int, level: str) -> None:
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if user:
            user.ai_sensitivity = level
            await self.user_repo.save_user(user)

    async def toggle_dnd(self, tg_id: int) -> tuple:
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if user:
            new_dnd = not user.is_dnd
            await self.user_repo.set_dnd(tg_id, new_dnd)
            if not new_dnd:
                pending = await self.user_repo.get_pending_notifications(tg_id)
                await self.user_repo.clear_pending_notifications(tg_id)
                return new_dnd, pending
            return new_dnd, []
        return False, []

    async def get_email_history(self, tg_id: int, limit: int = 10) -> list:
        return await self.user_repo.get_email_history(tg_id, limit=limit)

    async def get_stats(self, tg_id: int) -> dict:
        user_stats = await self.user_repo.get_user_stats(tg_id)
        cache_total = await self.cache_repo.get_total_cached() if self.cache_repo else 0
        return {**user_stats, "cache_total": cache_total}
