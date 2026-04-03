import os

# Must come before any src.* imports to satisfy config.py validation
os.environ.setdefault("EMAIL_USER", "test@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "testpass")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
os.environ.setdefault("APP_MODE", "personal")
os.environ.setdefault("ADMIN_TG_ID", "111222333")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")

import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.infrastructure.database.models import Base
from src.core.entities import User, Keyword, EmailMessage, PendingNotification


@pytest.fixture
async def db_session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    repo.get_by_telegram_id = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.save_user = AsyncMock()
    repo.add_keyword = AsyncMock()
    repo.remove_keyword = AsyncMock()
    repo.set_dnd = AsyncMock()
    repo.is_email_processed = AsyncMock(return_value=False)
    repo.mark_email_processed = AsyncMock()
    repo.get_email_history = AsyncMock(return_value=[])
    repo.get_user_stats = AsyncMock(return_value={"total_processed": 5, "important_count": 2})
    repo.add_pending_notification = AsyncMock()
    repo.get_pending_notifications = AsyncMock(return_value=[])
    repo.clear_pending_notifications = AsyncMock()
    return repo


@pytest.fixture
def mock_cache_repo():
    repo = AsyncMock()
    repo.get_cached_result = AsyncMock(return_value=None)
    repo.save_cached_result = AsyncMock()
    repo.get_total_cached = AsyncMock(return_value=10)
    return repo


@pytest.fixture
def mock_email_repo():
    repo = AsyncMock()
    repo.get_unread_emails = AsyncMock(return_value=[])
    repo.connect = AsyncMock()
    repo.disconnect = AsyncMock()
    return repo


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_ai_analyzer():
    analyzer = AsyncMock()
    analyzer.analyze_urgency = AsyncMock(
        return_value={"is_important": True, "reason": "Test reason"}
    )
    return analyzer


@pytest.fixture
def sample_user():
    return User(
        telegram_id=111222333,
        email="user@example.com",
        ai_sensitivity="medium",
        is_dnd=False,
        keywords=[
            Keyword(word="urgent", is_stop_word=False),
            Keyword(word="spam", is_stop_word=True),
        ],
    )


@pytest.fixture
def sample_email():
    return EmailMessage(
        uid="12345",
        sender="boss@company.com",
        subject="Urgent: deadline tomorrow",
        body="Please submit your report by end of day. https://portal.example.com/submit",
        date=datetime(2026, 4, 1, 10, 0),
        recipient_email="user@example.com",
    )


@pytest.fixture
def sample_pending():
    return PendingNotification(
        user_id=111222333,
        email_uid="12345",
        sender="boss@company.com",
        subject="Urgent meeting",
        body_snippet="Come to room 301...",
        ai_reason="Deadline approaching",
        triggered_word="urgent",
        action_url="https://portal.example.com/meeting",
    )
