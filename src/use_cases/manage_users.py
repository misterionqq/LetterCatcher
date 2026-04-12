import re
from typing import List, Optional

from passlib.context import CryptContext

from src.core.entities import User, Keyword, PendingNotification
from src.core.interfaces import IUserRepository, ICacheRepository

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ManageUsersUseCase:
    def __init__(self, user_repo: IUserRepository, cache_repo: ICacheRepository = None):
        self.user_repo = user_repo
        self.cache_repo = cache_repo

    # ------------------------------------------------------------------
    # Registration / auth
    # ------------------------------------------------------------------

    async def register_telegram_user(self, tg_id: int, email: str = None) -> User:
        """Create or update a user identified by Telegram ID. Returns user with id populated."""
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if not user:
            user = User(telegram_id=tg_id, email=email)
        else:
            if email:
                user.email = email
        return await self.user_repo.save_user(user)

    async def register_web_user(self, email: str, password: str) -> User:
        """Create a new web user with email + password. Raises ValueError on duplicate email."""
        if not _EMAIL_RE.match(email):
            raise ValueError("invalid_email")
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ValueError("email_taken")
        hashed = _pwd_context.hash(password)
        user = User(email=email, password_hash=hashed)
        return await self.user_repo.save_user(user)

    async def authenticate_web_user(self, email: str, password: str) -> Optional[User]:
        """Verify email+password. Returns User if valid, None otherwise."""
        user = await self.user_repo.get_by_email(email)
        if not user or not user.password_hash:
            return None
        if not _pwd_context.verify(password, user.password_hash):
            return None
        return user

    # ------------------------------------------------------------------
    # Profile lookup
    # ------------------------------------------------------------------

    async def get_user_profile(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        return await self.user_repo.get_by_id(user_id)

    async def get_user_profile_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Get user by Telegram ID (used by Telegram bot handlers)."""
        return await self.user_repo.get_by_telegram_id(tg_id)

    # ------------------------------------------------------------------
    # Settings (all accept internal user_id)
    # ------------------------------------------------------------------

    async def add_trigger_word(self, user_id: int, word: str) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if user:
            for kw in user.keywords:
                if kw.word == word.lower():
                    raise ValueError("duplicate_keyword")
        await self.user_repo.add_keyword(user_id, Keyword(word=word, is_stop_word=False))

    async def add_stop_word(self, user_id: int, word: str) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if user:
            for kw in user.keywords:
                if kw.word == word.lower():
                    if kw.is_stop_word:
                        raise ValueError("already_exists")
                    await self.user_repo.remove_keyword(user_id, word)
                    break
        await self.user_repo.add_keyword(user_id, Keyword(word=word, is_stop_word=True))

    async def set_email(self, user_id: int, email: str) -> None:
        if not _EMAIL_RE.match(email):
            raise ValueError("invalid_email")
        user = await self.user_repo.get_by_id(user_id)
        if user:
            user.email = email
            await self.user_repo.save_user(user)

    async def set_sensitivity(self, user_id: int, level: str) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if user:
            user.ai_sensitivity = level
            await self.user_repo.save_user(user)

    async def toggle_dnd(self, user_id: int) -> tuple:
        user = await self.user_repo.get_by_id(user_id)
        if user:
            new_dnd = not user.is_dnd
            await self.user_repo.set_dnd(user_id, new_dnd)
            if not new_dnd:
                pending = await self.user_repo.get_pending_notifications(user_id)
                await self.user_repo.clear_pending_notifications(user_id)
                return new_dnd, pending
            return new_dnd, []
        return False, []

    async def get_email_history(self, user_id: int, limit: int = 10) -> list:
        return await self.user_repo.get_email_history(user_id, limit=limit)

    async def get_stats(self, user_id: int) -> dict:
        user_stats = await self.user_repo.get_user_stats(user_id)
        cache_total = await self.cache_repo.get_total_cached() if self.cache_repo else 0
        return {**user_stats, "cache_total": cache_total}
