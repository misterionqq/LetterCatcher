from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class EmailMessage:
    uid: str
    sender: str
    subject: str
    body: str
    date: datetime

@dataclass
class Keyword:
    word: str
    is_stop_word: bool = False  # False = триггер, True = игнорировать письмо

@dataclass
class User:
    telegram_id: int
    email: Optional[str] = None 
    ai_sensitivity: str = "medium"  # low, medium, high
    keywords: List[Keyword] = field(default_factory=list)