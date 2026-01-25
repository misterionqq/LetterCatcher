from dataclasses import dataclass
from datetime import datetime

@dataclass
class EmailMessage:
    uid: str
    sender: str
    subject: str
    body: str
    date: datetime