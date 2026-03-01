from typing import List
from src.core.entities import EmailMessage
from src.core.interfaces import IEmailRepository

class CheckEmailUseCase:
    def __init__(self, repository: IEmailRepository):
        self.repository = repository

    def execute(self) -> List[EmailMessage]:
        self.repository.connect()
        try:
            emails = self.repository.get_unread_emails(limit=3)
            return emails
        finally:
            self.repository.disconnect()