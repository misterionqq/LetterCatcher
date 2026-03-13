import asyncio
import imaplib
import email
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List
from bs4 import BeautifulSoup

from src.core.interfaces import IEmailRepository
from src.core.entities import EmailMessage
from src.infrastructure.config import APP_MODE, EMAIL_USER

class ImapEmailRepository(IEmailRepository):
    def __init__(self, imap_server: str, email_user: str, email_password: str):
        self.imap_server = imap_server
        self.user = email_user
        self.password = email_password
        self.connection = None
    
    async def connect(self):
        await asyncio.to_thread(self._connect_sync)

    async def disconnect(self):
        await asyncio.to_thread(self._disconnect_sync)

    async def get_unread_emails(self, limit: int = 5) -> List[EmailMessage]:
        return await asyncio.to_thread(self._get_unread_sync, limit)

    def _connect_sync(self):
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server)
            self.connection.login(self.user, self.password)
        except Exception as e:
            raise ConnectionError(f"Ошибка подключения к IMAP: {e}")

    def _disconnect_sync(self):
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            try:
                self.connection.logout()
            except:
                pass

    def _get_unread_sync(self, limit: int) -> List[EmailMessage]:
        if not self.connection:
            self._connect_sync()

        self.connection.select("INBOX")
        

        date_since = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
        
        search_criteria = f'(UNSEEN SINCE "{date_since}")'
        status, messages = self.connection.search(None, search_criteria)
        
        if status != "OK" or not messages[0]:
            return []

        email_ids = messages[0].split()
        latest_email_ids = email_ids[-limit:]

        result_messages = []
        for e_id in reversed(latest_email_ids):
            res, msg_data = self.connection.fetch(e_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = self._decode_header_part(msg.get("Subject", "(Без темы)"))
                    
                    sender = self._decode_header_part(msg.get("From", "Неизвестно"))
                    
                    date_str = msg.get("Date")
                    try:
                        date_obj = parsedate_to_datetime(date_str) if date_str else datetime.now()
                    except:
                        date_obj = datetime.now()

                    body = self._extract_clean_body(msg)

                    recipient = self._determine_recipient(msg, body)

                    email_entity = EmailMessage(
                        uid=e_id.decode(),
                        sender=sender,
                        subject=subject,
                        body=body,
                        date=date_obj,
                        recipient_email=recipient
                    )
                    result_messages.append(email_entity)
        
        return result_messages

    def _decode_header_part(self, header_raw: str) -> str:
        decoded_parts = decode_header(header_raw)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding if encoding else "utf-8", errors="ignore")
            else:
                result += part
        return result

    def _extract_clean_body(self, msg) -> str:
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disp = str(part.get("Content-Disposition"))

                if "attachment" in disp:
                    continue

                if content_type == "text/plain":
                    try:
                        body_text += part.get_payload(decode=True).decode(errors="ignore")
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        body_html += part.get_payload(decode=True).decode(errors="ignore")
                    except:
                        pass
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True).decode(errors="ignore")
                if content_type == "text/html":
                    body_html = payload
                else:
                    body_text = payload
            except:
                pass

        if body_text.strip():
            return body_text.strip()
        elif body_html.strip():
            soup = BeautifulSoup(body_html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        
        return "(Пустое письмо или нечитаемый формат)"

    def _determine_recipient(self, msg, body: str) -> str:
        if APP_MODE == "personal":
            return self.user

        forwarded_to = msg.get("X-Forwarded-To") or msg.get("Delivered-To")
        if forwarded_to:
            return self._decode_header_part(forwarded_to)
        
        match = re.search(r"To:\s*([\w\.-]+@[\w\.-]+)", body)
        if match:
            return match.group(1)

        return self.user 
    
    