from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from src.core.entities import EmailMessage, User, Keyword, PendingNotification

class IEmailRepository(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def get_unread_emails(self, limit: int = 5) -> List[EmailMessage]:
        pass

class IUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_telegram_id(self, tg_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save_user(self, user: User) -> "User":
        pass

    @abstractmethod
    async def add_keyword(self, user_id: int, keyword: Keyword) -> None:
        pass

    @abstractmethod
    async def remove_keyword(self, user_id: int, word: str) -> None:
        pass

    @abstractmethod
    async def set_dnd(self, user_id: int, is_dnd: bool) -> None:
        pass

    @abstractmethod
    async def is_email_processed(self, user_id: int, email_uid: str) -> bool:
        pass

    @abstractmethod
    async def mark_email_processed(self, user_id: int, email_uid: str,
                                   sender: str = "", subject: str = "",
                                   is_important: bool = False, **kwargs) -> None:
        pass

    @abstractmethod
    async def get_email_history(self, user_id: int, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def get_user_stats(self, user_id: int) -> dict:
        pass

    @abstractmethod
    async def add_pending_notification(self, notification: PendingNotification) -> None:
        pass

    @abstractmethod
    async def get_pending_notifications(self, user_id: int) -> List[PendingNotification]:
        pass

    @abstractmethod
    async def clear_pending_notifications(self, user_id: int) -> None:
        pass

class ICacheRepository(ABC):
    @abstractmethod
    async def get_cached_result(self, text_hash: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def save_cached_result(self, text_hash: str, is_important: bool, reason: str) -> None:
        pass

    @abstractmethod
    async def get_total_cached(self) -> int:
        pass

class IVerificationTokenRepository(ABC):
    @abstractmethod
    async def create_token(self, user_id: int, token_type: str, expires_at: datetime,
                           payload: str = None) -> str:
        pass

    @abstractmethod
    async def get_valid_token(self, token: str, token_type: str) -> Optional[dict]:
        """Returns {user_id, payload} if token is valid and not expired/used, else None."""
        pass

    @abstractmethod
    async def mark_used(self, token: str) -> None:
        pass

    @abstractmethod
    async def cleanup_expired(self) -> None:
        pass


class IAIAnalyzer(ABC):
    @abstractmethod
    async def analyze_urgency(self, subject: str, text: str) -> dict:
        pass
