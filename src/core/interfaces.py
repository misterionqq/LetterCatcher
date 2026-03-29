from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.entities import EmailMessage, User, Keyword

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
    async def get_by_telegram_id(self, tg_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save_user(self, user: User) -> None:
        pass

    @abstractmethod
    async def add_keyword(self, tg_id: int, keyword: Keyword) -> None:
        pass

    @abstractmethod
    async def remove_keyword(self, tg_id: int, word: str) -> None:
        pass

    @abstractmethod
    async def set_dnd(self, tg_id: int, is_dnd: bool) -> None:
        pass

    @abstractmethod
    async def is_email_processed(self, user_id: int, email_uid: str) -> bool:
        pass

    @abstractmethod
    async def mark_email_processed(self, user_id: int, email_uid: str) -> None:
        pass

class ICacheRepository(ABC):
    @abstractmethod
    async def get_cached_result(self, text_hash: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def save_cached_result(self, text_hash: str, is_important: bool, reason: str) -> None:
        pass

class IAIAnalyzer(ABC):
    @abstractmethod
    async def analyze_urgency(self, subject: str, text: str) -> dict:
        pass