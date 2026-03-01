import imaplib
import email
from email.header import decode_header
from typing import List
from datetime import datetime
from src.core.interfaces import IEmailRepository
from src.core.entities import EmailMessage

class ImapEmailRepository(IEmailRepository):
    def __init__(self, imap_server: str, email_user: str, email_password: str):
        self.imap_server = imap_server
        self.user = email_user
        self.password = email_password
        self.connection = None

    def connect(self):
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server)
            self.connection.login(self.user, self.password)
            print(f"Успешное подключение к {self.imap_server}")
        except Exception as e:
            print(f"Ошибка подключения к IMAP: {e}")
            raise

    def disconnect(self):
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection.logout()

    def get_unread_emails(self, limit: int = 5) -> List[EmailMessage]:
        if not self.connection:
            raise ConnectionError("Нет подключения к IMAP серверу")

        self.connection.select("INBOX")

        status, messages = self.connection.search(None, "UNSEEN")
        
        if status != "OK":
            return []

        email_ids = messages[0].split()
        latest_email_ids = email_ids[-limit:]

        result_messages = []

        for e_id in reversed(latest_email_ids):
            res, msg_data = self.connection.fetch(e_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    sender = msg.get("From")
                    
                    date_str = msg.get("Date")
                    
                    date_obj = datetime.now() # TODO: парсер времени (?) 

                    body = self._get_email_body(msg)

                    email_entity = EmailMessage(
                        uid=e_id.decode(),
                        sender=sender,
                        subject=subject,
                        body=body,
                        date=date_obj
                    )
                    result_messages.append(email_entity)
        
        return result_messages

    def _get_email_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        return part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            try:
                return msg.get_payload(decode=True).decode()
            except:
                pass
        return "(Текст не найден или зашифрован)"