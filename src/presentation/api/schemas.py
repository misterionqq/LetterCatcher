from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


# --- Auth ---

class TokenRequest(BaseModel):
    """Telegram Login Widget authentication data."""
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    photo_url: str = ""
    auth_date: int
    hash: str


class WebRegisterRequest(BaseModel):
    """Web / mobile registration with email + password."""
    email: str
    password: str = Field(..., min_length=8)


class WebLoginRequest(BaseModel):
    """Web / mobile login with email + password."""
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- User ---

class KeywordOut(BaseModel):
    word: str
    is_stop_word: bool


class UserOut(BaseModel):
    telegram_id: Optional[int] = None
    email: Optional[str] = None
    email_verified: bool = False
    ai_sensitivity: str
    is_dnd: bool
    keywords: List[KeywordOut] = []


class SetEmailRequest(BaseModel):
    email: str


class SetSensitivityRequest(BaseModel):
    level: str = Field(..., pattern="^(low|medium|high)$")


class AddKeywordRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)


class AddStopWordRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)


# --- Device token (FCM push) ---

class DeviceTokenRequest(BaseModel):
    token: str = Field(..., min_length=1)
    platform: str = Field(default="android", pattern="^(android|ios|web)$")


# --- Common ---

class AttachmentInfo(BaseModel):
    name: str
    content_type: str
    size: int  # bytes


# --- Email history ---

class EmailHistoryItem(BaseModel):
    email_uid: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    is_important: bool
    processed_at: Optional[datetime] = None
    date: Optional[str] = None
    body_full: str = ""
    body_html: Optional[str] = None
    ai_reason: str = ""
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None
    links: List[str] = []
    attachments: List[AttachmentInfo] = []


# --- Stats ---

class StatsOut(BaseModel):
    total_processed: int
    important_count: int
    cache_total: int


# --- DND ---

class DndToggleOut(BaseModel):
    is_dnd: bool
    pending_count: int


# --- Pending notification ---

class PendingNotificationOut(BaseModel):
    id: Optional[int] = None
    email_uid: str
    sender: str
    subject: str
    body_snippet: str
    body_full: str = ""
    body_html: Optional[str] = None
    links: List[str] = []
    attachments: List[AttachmentInfo] = []
    ai_reason: str
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None
    created_at: Optional[datetime] = None


# --- Server info ---

class ServerInfoOut(BaseModel):
    app_mode: str
    client_mode: str
    forwarding_email: Optional[str] = None


# --- Auth: password reset ---

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class MessageResponse(BaseModel):
    message: str


# --- Health ---

class HealthOut(BaseModel):
    status: str = "ok"
    database: str = "ok"
    scanner: str = "unknown"


# --- WebSocket notification ---

class WsNotification(BaseModel):
    type: str = "email_notification"
    email_uid: str
    sender: str
    subject: str
    date: Optional[str] = None
    is_important: bool = False
    body_snippet: str
    body_full: str = ""
    body_html: Optional[str] = None
    links: List[str] = []
    attachments: List[AttachmentInfo] = []
    ai_reason: str = ""
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None
