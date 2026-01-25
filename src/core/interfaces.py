from abc import ABC, abstractmethod
from typing import List
from src.core.entities import EmailMessage

class IEmailRepository(ABC):
    
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def get_unread_emails(self, limit: int = 5) -> List[EmailMessage]:
        pass