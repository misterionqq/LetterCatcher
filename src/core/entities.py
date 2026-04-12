from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

@dataclass
class EmailMessage:
    uid: str
    sender: str
    subject: str
    body: str
    date: datetime
    recipient_email: Optional[str] = None
    body_html: Optional[str] = None
    links: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Keyword:
    word: str
    is_stop_word: bool = False

@dataclass
class PendingNotification:
    user_id: int = 0
    email_uid: str = ""
    sender: str = ""
    subject: str = ""
    body_snippet: str = "" 
    body_full: str = ""         
    body_html: Optional[str] = None
    links: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    ai_reason: str = ""
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None   
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: Optional[int] = None

@dataclass
class User:
    id: Optional[int] = None              
    telegram_id: Optional[int] = None     # None for web-only users
    email: Optional[str] = None
    ai_sensitivity: str = "medium"
    is_dnd: bool = False
    keywords: List[Keyword] = field(default_factory=list)
    password_hash: Optional[str] = None   # None for telegram-only users
