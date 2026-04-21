import asyncio
import imaplib
import email
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import nh3

from src.core.interfaces import IEmailRepository
from src.core.entities import EmailMessage
from src.infrastructure.config import APP_MODE, EMAIL_USER, SANITIZE_HTML

_LINK_NOISE = ("unsubscribe", "track", "pixel", "open.php", "click.php", "beacon",
               "list-unsubscribe", "mailto:", "javascript:")

_SAFE_TAGS = {
    "div", "span", "p", "br", "hr", "center",
    "b", "strong", "i", "em", "u", "s", "strike", "del", "ins",
    "sub", "sup", "small", "font", "mark", "abbr", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "tr", "td", "th", "thead", "tbody", "tfoot",
    "caption", "col", "colgroup",
    "a", "img",
    "blockquote",
    "style",
}

_SAFE_ATTRS = {
    "*": {"style", "class", "id", "dir", "lang", "title",
           "width", "height", "align", "valign", "bgcolor", "color"},
    "a": {"href", "target", "name"},
    "img": {"src", "alt", "border"},
    "font": {"face", "size", "color"},
    "table": {"border", "cellpadding", "cellspacing"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "col": {"span"},
    "colgroup": {"span"},
    "ol": {"start", "type"},
    "li": {"value"},
}


def _sanitize_email_html(raw_html: str) -> str:
    if not raw_html or not SANITIZE_HTML:
        return raw_html
    return nh3.clean(
        raw_html,
        tags=_SAFE_TAGS,
        clean_content_tags={"script"},
        attributes=_SAFE_ATTRS,
        generic_attribute_prefixes={"data-"},
        url_schemes={"http", "https", "mailto", "cid"},
        strip_comments=True,
        link_rel="noopener noreferrer",
    )


_IMAP_MAX_CONN_AGE = 600 


class ImapEmailRepository(IEmailRepository):
    def __init__(self, imap_server: str, email_user: str, email_password: str):
        self.imap_server = imap_server
        self.user = email_user
        self.password = email_password
        self.connection = None
        self._connected_at: float = 0

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
            self._connected_at = time.monotonic()
        except Exception as e:
            self.connection = None
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

    def _ensure_alive(self):
        age = time.monotonic() - self._connected_at
        if not self.connection or age > _IMAP_MAX_CONN_AGE:
            logging.debug(f"IMAP: переподключение (возраст соединения: {age:.0f}с)")
            self._force_disconnect()
            self._connect_sync()
            return

        try:
            status, _ = self.connection.noop()
            if status != "OK":
                raise imaplib.IMAP4.error("NOOP failed")
        except Exception:
            logging.debug("IMAP: NOOP failed, переподключение")
            self._force_disconnect()
            self._connect_sync()

    def _force_disconnect(self):
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def _get_unread_sync(self, limit: int) -> List[EmailMessage]:
        self._ensure_alive()
        try:
            return self._fetch_unread_sync(limit)
        except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError):
            logging.warning("IMAP: ошибка при чтении, переподключение...")
            self._force_disconnect()
            self._connect_sync()
            return self._fetch_unread_sync(limit)

    def _fetch_unread_sync(self, limit: int) -> List[EmailMessage]:
        if not self.connection:
            self._connect_sync()

        # TODO: вынести список папок в .env (IMAP_FOLDERS)
        folders = ["INBOX", "[Gmail]/Spam"]

        result_messages: List[EmailMessage] = []
        for folder in folders:
            try:
                status, _ = self.connection.select(folder)
                if status != "OK":
                    continue
            except imaplib.IMAP4.abort:
                raise  # connection dead — let outer handler reconnect
            except imaplib.IMAP4.error:
                continue  # folder doesn't exist, skip

            date_since = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
            search_criteria = f'(UNSEEN SINCE "{date_since}")'
            status, messages = self.connection.search(None, search_criteria)

            if status != "OK" or not messages[0]:
                continue

            email_ids = messages[0].split()
            remaining = limit - len(result_messages)
            if remaining <= 0:
                break
            latest_email_ids = email_ids[-remaining:]

            for e_id in reversed(latest_email_ids):
                res, msg_data = self.connection.fetch(e_id, "(RFC822)")

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        subject = self._decode_header_part(msg.get("Subject", "(Без темы)"))
                        sender = self._decode_header_part(msg.get("From", "Неизвестно"))

                        date_str = msg.get("Date")
                        try:
                            date_obj = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()
                            if date_obj.tzinfo is not None:
                                date_obj = date_obj.astimezone(timezone.utc).replace(tzinfo=None)
                        except Exception:
                            date_obj = datetime.utcnow()

                        plain_body, html_body = self._parse_body(msg)
                        links = self._extract_links(html_body, plain_body)
                        attachments = self._extract_attachments(msg)
                        recipient = self._determine_recipient(msg, plain_body)

                        uid_str = e_id.decode()
                        if folder != "INBOX":
                            uid_str = f"spam:{uid_str}"

                        email_entity = EmailMessage(
                            uid=uid_str,
                            sender=sender,
                            subject=subject,
                            body=plain_body,
                            date=date_obj,
                            recipient_email=recipient,
                            body_html=html_body or None,
                            links=links,
                            attachments=attachments,
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

    def _parse_body(self, msg) -> Tuple[str, str]:
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
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

        if not body_text.strip() and body_html.strip():
            soup = BeautifulSoup(body_html, "html.parser")
            body_text = soup.get_text(separator="\n", strip=True)

        return (
            body_text.strip() or "(Пустое письмо или нечитаемый формат)",
            _sanitize_email_html(body_html.strip()),
        )

    def _extract_links(self, html_body: str, plain_body: str) -> List[str]:
        seen = set()
        links = []

        def _add(url: str):
            url = url.strip().rstrip(".,;)")
            if len(url) < 10 or len(url) > 500:
                return
            if any(n in url.lower() for n in _LINK_NOISE):
                return
            if url not in seen:
                seen.add(url)
                links.append(url)

        if html_body:
            soup = BeautifulSoup(html_body, "html.parser")
            for tag in soup.find_all("a", href=True):
                href = tag["href"].strip()
                if href.startswith("http"):
                    _add(href)
        else:
            for match in re.finditer(r'https?://[^\s<>"\'\]]+', plain_body):
                _add(match.group(0))

        return links

    def _extract_attachments(self, msg) -> List[Dict[str, Any]]:
        attachments = []
        if not msg.is_multipart():
            return attachments

        for part in msg.walk():
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" not in disp:
                continue
            filename_raw = part.get_filename()
            if not filename_raw:
                continue
            filename = self._decode_header_part(filename_raw)
            content_type = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
            except:
                size = 0
            attachments.append({
                "name": filename,
                "content_type": content_type,
                "size": size,
            })

        return attachments

    def _determine_recipient(self, msg, body: str) -> str:
        if APP_MODE == "personal":
            return self.user

        for header in ("To", "X-Original-To"):
            value = msg.get(header)
            if value:
                decoded = self._decode_header_part(value)
                match = re.search(r"[\w\.\+\-]+@[\w\.\-]+", decoded)
                if match:
                    addr = match.group(0)
                    if addr.lower() != self.user.lower():
                        return addr

        for header in ("X-Forwarded-To", "Delivered-To"):
            value = msg.get(header)
            if value:
                decoded = self._decode_header_part(value)
                match = re.search(r"[\w\.\+\-]+@[\w\.\-]+", decoded)
                if match:
                    addr = match.group(0)
                    if addr.lower() != self.user.lower():
                        return addr

        match = re.search(r"To:\s*([\w\.\+\-]+@[\w\.\-]+)", body)
        if match:
            return match.group(1)

        return self.user
    