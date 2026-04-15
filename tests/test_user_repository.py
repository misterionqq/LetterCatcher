import pytest
from datetime import datetime

from src.core.entities import User, Keyword, PendingNotification
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


@pytest.fixture
def repo(db_session_factory):
    return SQLAlchemyUserRepository(session_factory=db_session_factory)


async def _create_user(repo, tg_id=100, email="test@mail.com") -> User:
    user = User(telegram_id=tg_id, email=email)
    saved = await repo.save_user(user)
    return saved


# --- Basic CRUD ---

async def test_save_and_get_by_tg_id(repo):
    saved = await _create_user(repo)
    result = await repo.get_by_telegram_id(100)
    assert result is not None
    assert result.telegram_id == 100
    assert result.email == "test@mail.com"
    assert result.id == saved.id


async def test_get_by_id(repo):
    saved = await _create_user(repo)
    result = await repo.get_by_id(saved.id)
    assert result is not None
    assert result.telegram_id == 100


async def test_get_not_found(repo):
    assert await repo.get_by_telegram_id(999) is None
    assert await repo.get_by_id(999) is None


async def test_update_existing_user(repo):
    saved = await _create_user(repo)
    user = User(id=saved.id, telegram_id=100, email="new@mail.com")
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


# --- email_verified ---

async def test_email_verified_default_false(repo):
    saved = await _create_user(repo)
    result = await repo.get_by_id(saved.id)
    assert result.email_verified is False


async def test_email_verified_update(repo):
    saved = await _create_user(repo)
    saved.email_verified = True
    await repo.save_user(saved)

    result = await repo.get_by_id(saved.id)
    assert result.email_verified is True


# --- password_hash ---

async def test_password_hash_saved(repo):
    user = User(email="web@user.com", password_hash="hashed_pw_123")
    saved = await repo.save_user(user)

    result = await repo.get_by_id(saved.id)
    assert result.password_hash == "hashed_pw_123"


# --- Keywords ---

async def test_add_keyword_and_retrieve(repo):
    saved = await _create_user(repo)
    await repo.add_keyword(saved.id, Keyword(word="deadline", is_stop_word=False))

    user = await repo.get_by_id(saved.id)
    assert len(user.keywords) == 1
    assert user.keywords[0].word == "deadline"
    assert user.keywords[0].is_stop_word is False


async def test_add_trigger_and_stop_word(repo):
    saved = await _create_user(repo)
    await repo.add_keyword(saved.id, Keyword(word="urgent", is_stop_word=False))
    await repo.add_keyword(saved.id, Keyword(word="spam", is_stop_word=True))

    user = await repo.get_by_id(saved.id)
    assert len(user.keywords) == 2
    words = {kw.word: kw.is_stop_word for kw in user.keywords}
    assert words["urgent"] is False
    assert words["spam"] is True


async def test_remove_keyword(repo):
    saved = await _create_user(repo)
    await repo.add_keyword(saved.id, Keyword(word="test"))
    await repo.remove_keyword(saved.id, "test")

    user = await repo.get_by_id(saved.id)
    assert len(user.keywords) == 0


async def test_remove_nonexistent_keyword(repo):
    saved = await _create_user(repo)
    await repo.remove_keyword(saved.id, "nonexistent")  # should not raise


# --- DND ---

async def test_set_dnd(repo):
    saved = await _create_user(repo)
    await repo.set_dnd(saved.id, True)

    user = await repo.get_by_id(saved.id)
    assert user.is_dnd is True

    await repo.set_dnd(saved.id, False)
    user = await repo.get_by_id(saved.id)
    assert user.is_dnd is False


# --- Processed emails ---

async def test_mark_and_check_processed(repo):
    saved = await _create_user(repo)
    assert await repo.is_email_processed(saved.id, "uid-1") is False

    await repo.mark_email_processed(saved.id, "uid-1", sender="a@b.com", subject="Hi", is_important=True)
    assert await repo.is_email_processed(saved.id, "uid-1") is True


async def test_is_email_processed_false(repo):
    saved = await _create_user(repo)
    assert await repo.is_email_processed(saved.id, "unknown-uid") is False


async def test_get_email_history_ordering(repo):
    saved = await _create_user(repo)
    await repo.mark_email_processed(saved.id, "uid-1", sender="a", subject="First", is_important=False)
    await repo.mark_email_processed(saved.id, "uid-2", sender="b", subject="Second", is_important=True)
    await repo.mark_email_processed(saved.id, "uid-3", sender="c", subject="Third", is_important=True)

    history = await repo.get_email_history(saved.id, limit=2)
    assert len(history) == 2
    assert history[0]["subject"] == "Third"


async def test_get_email_history_with_extra_fields(repo):
    saved = await _create_user(repo)
    await repo.mark_email_processed(
        saved.id, "uid-1", sender="a", subject="Test", is_important=True,
        body_full="Full body text", body_html="<p>HTML</p>",
        ai_reason="Important", triggered_word="urgent",
        action_url="https://example.com",
        links=["https://example.com"], attachments=[{"name": "file.pdf", "content_type": "application/pdf", "size": 1024}],
    )

    history = await repo.get_email_history(saved.id, limit=1)
    assert len(history) == 1
    item = history[0]
    assert item["body_full"] == "Full body text"
    assert item["body_html"] == "<p>HTML</p>"
    assert item["ai_reason"] == "Important"
    assert item["triggered_word"] == "urgent"
    assert item["links"] == ["https://example.com"]
    assert len(item["attachments"]) == 1


async def test_get_user_stats(repo):
    saved = await _create_user(repo)
    await repo.mark_email_processed(saved.id, "uid-1", sender="a", subject="A", is_important=True)
    await repo.mark_email_processed(saved.id, "uid-2", sender="b", subject="B", is_important=False)
    await repo.mark_email_processed(saved.id, "uid-3", sender="c", subject="C", is_important=True)

    stats = await repo.get_user_stats(saved.id)
    assert stats["total_processed"] == 3
    assert stats["important_count"] == 2


# --- Pending notifications ---

async def test_pending_notification_cycle(repo):
    saved = await _create_user(repo)

    notif = PendingNotification(
        user_id=saved.id, email_uid="uid-1", sender="boss@co.com",
        subject="Meeting", body_snippet="Room 301", ai_reason="Deadline",
    )
    await repo.add_pending_notification(notif)

    pending = await repo.get_pending_notifications(saved.id)
    assert len(pending) == 1
    assert pending[0].subject == "Meeting"
    assert pending[0].sender == "boss@co.com"

    await repo.clear_pending_notifications(saved.id)
    pending = await repo.get_pending_notifications(saved.id)
    assert len(pending) == 0


async def test_pending_notification_with_rich_fields(repo):
    saved = await _create_user(repo)

    notif = PendingNotification(
        user_id=saved.id, email_uid="uid-2", sender="a@b.com",
        subject="Test", body_snippet="snippet",
        body_full="full body", body_html="<p>html</p>",
        links=["https://example.com"], attachments=[{"name": "f.pdf", "content_type": "application/pdf", "size": 100}],
        ai_reason="reason", triggered_word="urgent",
        action_url="https://example.com/action",
    )
    await repo.add_pending_notification(notif)

    pending = await repo.get_pending_notifications(saved.id)
    assert len(pending) == 1
    p = pending[0]
    assert p.body_full == "full body"
    assert p.links == ["https://example.com"]
    assert len(p.attachments) == 1


# --- Device tokens ---

async def test_save_and_get_device_tokens(repo):
    saved = await _create_user(repo)
    await repo.save_device_token(saved.id, "fcm-token-1", "android")
    await repo.save_device_token(saved.id, "fcm-token-2", "ios")

    tokens = await repo.get_device_tokens(saved.id)
    assert set(tokens) == {"fcm-token-1", "fcm-token-2"}


async def test_save_device_token_duplicate_ignored(repo):
    saved = await _create_user(repo)
    await repo.save_device_token(saved.id, "fcm-token-1")
    await repo.save_device_token(saved.id, "fcm-token-1")  # duplicate

    tokens = await repo.get_device_tokens(saved.id)
    assert len(tokens) == 1


async def test_remove_device_tokens(repo):
    saved = await _create_user(repo)
    await repo.save_device_token(saved.id, "token-a")
    await repo.save_device_token(saved.id, "token-b")

    await repo.remove_device_tokens(["token-a"])

    tokens = await repo.get_device_tokens(saved.id)
    assert tokens == ["token-b"]


async def test_remove_device_tokens_empty_list(repo):
    saved = await _create_user(repo)
    await repo.remove_device_tokens([])  # should not raise
