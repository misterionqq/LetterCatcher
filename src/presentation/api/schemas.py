from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- Auth ---

class TokenRequest(BaseModel):
    telegram_id: int
    telegram_hash: str = Field(..., description="HMAC-SHA256 hash for Telegram Login Widget verification")


class RegisterRequest(BaseModel):
    telegram_id: int
    telegram_hash: str = Field(..., description="HMAC-SHA256 hash for Telegram Login Widget verification")
    email: Optional[str] = Field(None, description="Corporate email address (can be set later)")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- User ---

class KeywordOut(BaseModel):
    word: str
    is_stop_word: bool


class UserOut(BaseModel):
    telegram_id: int
    email: Optional[str] = None
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


# --- Email history ---

class EmailHistoryItem(BaseModel):
    email_uid: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    is_important: bool
    processed_at: Optional[datetime] = None


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
    ai_reason: str
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None
    created_at: Optional[datetime] = None


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
    body_snippet: str
    ai_reason: str
    triggered_word: Optional[str] = None
    action_url: Optional[str] = None
