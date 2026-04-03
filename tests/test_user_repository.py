import pytest
from datetime import datetime

from src.core.entities import User, Keyword, PendingNotification
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


@pytest.fixture
def repo(db_session_factory):
    return SQLAlchemyUserRepository(session_factory=db_session_factory)


async def _create_user(repo, tg_id=100, email="test@mail.com"):
    user = User(telegram_id=tg_id, email=email)
    await repo.save_user(user)
    return user


# --- Basic CRUD ---

async def test_save_and_get_by_tg_id(repo):
    await _create_user(repo)
    result = await repo.get_by_telegram_id(100)
    assert result is not None
    assert result.telegram_id == 100
    assert result.email == "test@mail.com"


async def test_get_not_found(repo):
    assert await repo.get_by_telegram_id(999) is None


async def test_update_existing_user(repo):
    await _create_user(repo)
    user = User(telegram_id=100, email="new@mail.com")
    await repo.save_user(user)

    result = await repo.get_by_telegram_id(100)
    assert result.email == "new@mail.com"


async def test_get_by_email(repo):
    await _create_user(repo, email="find@me.com")
    result = await repo.get_by_email("find@me.com")
    assert result is not None
    assert result.telegram_id == 100


async def test_get_by_email_not_found(repo):
    assert await repo.get_by_email("nope@nope.com") is None


# --- Keywords ---

async def test_add_keyword_and_retrieve(repo):
    await _create_user(repo)
    await repo.add_keyword(100, Keyword(word="deadline", is_stop_word=False))

    user = await repo.get_by_telegram_id(100)
    assert len(user.keywords) == 1
    assert user.keywords[0].word == "deadline"
    assert user.keywords[0].is_stop_word is False


async def test_add_trigger_and_stop_word(repo):
    await _create_user(repo)
    await repo.add_keyword(100, Keyword(word="urgent", is_stop_word=False))
    await repo.add_keyword(100, Keyword(word="spam", is_stop_word=True))

    user = await repo.get_by_telegram_id(100)
    assert len(user.keywords) == 2
    words = {kw.word: kw.is_stop_word for kw in user.keywords}
    assert words["urgent"] is False
    assert words["spam"] is True


async def test_remove_keyword(repo):
    await _create_user(repo)
    await repo.add_keyword(100, Keyword(word="test"))
    await repo.remove_keyword(100, "test")

    user = await repo.get_by_telegram_id(100)
    assert len(user.keywords) == 0


async def test_remove_nonexistent_keyword(repo):
    await _create_user(repo)
    await repo.remove_keyword(100, "nonexistent")  # should not raise


# --- DND ---

async def test_set_dnd(repo):
    await _create_user(repo)
    await repo.set_dnd(100, True)

    user = await repo.get_by_telegram_id(100)
    assert user.is_dnd is True

    await repo.set_dnd(100, False)
    user = await repo.get_by_telegram_id(100)
    assert user.is_dnd is False


# --- Processed emails ---

async def test_mark_and_check_processed(repo):
    await _create_user(repo)
    assert await repo.is_email_processed(100, "uid-1") is False

    await repo.mark_email_processed(100, "uid-1", sender="a@b.com", subject="Hi", is_important=True)
    assert await repo.is_email_processed(100, "uid-1") is True


async def test_is_email_processed_false(repo):
    await _create_user(repo)
    assert await repo.is_email_processed(100, "unknown-uid") is False


async def test_get_email_history_ordering(repo):
    await _create_user(repo)
    await repo.mark_email_processed(100, "uid-1", sender="a", subject="First", is_important=False)
    await repo.mark_email_processed(100, "uid-2", sender="b", subject="Second", is_important=True)
    await repo.mark_email_processed(100, "uid-3", sender="c", subject="Third", is_important=True)

    history = await repo.get_email_history(100, limit=2)
    assert len(history) == 2
    assert history[0]["subject"] == "Third"


async def test_get_user_stats(repo):
    await _create_user(repo)
    await repo.mark_email_processed(100, "uid-1", sender="a", subject="A", is_important=True)
    await repo.mark_email_processed(100, "uid-2", sender="b", subject="B", is_important=False)
    await repo.mark_email_processed(100, "uid-3", sender="c", subject="C", is_important=True)

    stats = await repo.get_user_stats(100)
    assert stats["total_processed"] == 3
    assert stats["important_count"] == 2


# --- Pending notifications ---

async def test_pending_notification_cycle(repo):
    await _create_user(repo)

    notif = PendingNotification(
        user_id=100, email_uid="uid-1", sender="boss@co.com",
        subject="Meeting", body_snippet="Room 301", ai_reason="Deadline",
    )
    await repo.add_pending_notification(notif)

    pending = await repo.get_pending_notifications(100)
    assert len(pending) == 1
    assert pending[0].subject == "Meeting"
    assert pending[0].sender == "boss@co.com"

    await repo.clear_pending_notifications(100)
    pending = await repo.get_pending_notifications(100)
    assert len(pending) == 0
