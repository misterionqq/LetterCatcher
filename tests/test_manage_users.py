import pytest
from unittest.mock import AsyncMock

from src.core.entities import User, Keyword, PendingNotification
from src.use_cases.manage_users import ManageUsersUseCase


@pytest.fixture
def use_case(mock_user_repo, mock_cache_repo, mock_token_repo, mock_email_sender):
    return ManageUsersUseCase(
        user_repo=mock_user_repo, cache_repo=mock_cache_repo,
        token_repo=mock_token_repo, email_sender=mock_email_sender,
    )


@pytest.fixture
def use_case_no_verification(mock_user_repo, mock_cache_repo):
    """Use case without token_repo / email_sender (verification unavailable)."""
    return ManageUsersUseCase(user_repo=mock_user_repo, cache_repo=mock_cache_repo)


# ================================================================
# register_telegram_user
# ================================================================

async def test_register_telegram_user_new(use_case, mock_user_repo):
    new_user = User(id=1, telegram_id=100, email="a@b.com")
    mock_user_repo.get_by_telegram_id.return_value = None
    mock_user_repo.save_user.return_value = new_user

    result = await use_case.register_telegram_user(tg_id=100, email="a@b.com")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.telegram_id == 100
    assert saved.email == "a@b.com"
    assert result == new_user


async def test_register_telegram_user_update_email(use_case, mock_user_repo):
    existing = User(id=1, telegram_id=100, email="old@b.com")
    updated = User(id=1, telegram_id=100, email="new@b.com")
    mock_user_repo.get_by_telegram_id.return_value = existing
    mock_user_repo.save_user.return_value = updated

    result = await use_case.register_telegram_user(tg_id=100, email="new@b.com")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email == "new@b.com"


# ================================================================
# register_web_user
# ================================================================

async def test_register_web_user_success(use_case, mock_user_repo, mock_token_repo, mock_email_sender):
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.save_user.return_value = User(id=1, email="test@mail.com", email_verified=False)

    result = await use_case.register_web_user("test@mail.com", "password123", base_url="http://localhost")

    assert result.id == 1
    assert result.email_verified is False
    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email == "test@mail.com"
    assert saved.password_hash is not None
    assert saved.email_verified is False
    mock_token_repo.create_token.assert_called_once()
    mock_email_sender.send_verification_email.assert_called_once()


async def test_register_web_user_duplicate_email(use_case, mock_user_repo):
    mock_user_repo.get_by_email.return_value = User(id=1, email="taken@mail.com")

    with pytest.raises(ValueError, match="email_taken"):
        await use_case.register_web_user("taken@mail.com", "password123")


async def test_register_web_user_invalid_email(use_case):
    with pytest.raises(ValueError, match="invalid_email"):
        await use_case.register_web_user("not-an-email", "password123")


async def test_register_web_user_no_verification(use_case_no_verification, mock_user_repo):
    """When token_repo/email_sender are None, user is created but no email sent."""
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.save_user.return_value = User(id=1, email="test@mail.com")

    result = await use_case_no_verification.register_web_user("test@mail.com", "password123")
    assert result.id == 1


# ================================================================
# authenticate_web_user
# ================================================================

async def test_authenticate_web_user_success(use_case, mock_user_repo):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd.hash("correct_password")
    user = User(id=1, email="test@mail.com", password_hash=hashed)
    mock_user_repo.get_by_email.return_value = user

    result = await use_case.authenticate_web_user("test@mail.com", "correct_password")
    assert result is not None
    assert result.id == 1


async def test_authenticate_web_user_wrong_password(use_case, mock_user_repo):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd.hash("correct_password")
    user = User(id=1, email="test@mail.com", password_hash=hashed)
    mock_user_repo.get_by_email.return_value = user

    result = await use_case.authenticate_web_user("test@mail.com", "wrong_password")
    assert result is None


async def test_authenticate_web_user_not_found(use_case, mock_user_repo):
    """Should still hash a dummy password (timing attack protection)."""
    mock_user_repo.get_by_email.return_value = None

    result = await use_case.authenticate_web_user("nobody@mail.com", "password")
    assert result is None


async def test_authenticate_web_user_no_password_hash(use_case, mock_user_repo):
    """Telegram-only user has no password_hash."""
    user = User(id=1, email="test@mail.com", password_hash=None)
    mock_user_repo.get_by_email.return_value = user

    result = await use_case.authenticate_web_user("test@mail.com", "password")
    assert result is None


# ================================================================
# verify_email
# ================================================================

async def test_verify_email_success(use_case, mock_user_repo, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = {"user_id": 1, "payload": None}
    mock_user_repo.get_by_id.return_value = User(id=1, email="a@b.com", email_verified=False)
    mock_user_repo.save_user.return_value = User(id=1, email="a@b.com", email_verified=True)

    result = await use_case.verify_email("valid-token")

    assert result is True
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email_verified is True
    mock_token_repo.mark_used.assert_called_once_with("valid-token")


async def test_verify_email_invalid_token(use_case, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = None

    result = await use_case.verify_email("bad-token")
    assert result is False


async def test_verify_email_no_token_repo(use_case_no_verification):
    result = await use_case_no_verification.verify_email("any-token")
    assert result is False


# ================================================================
# resend_verification
# ================================================================

async def test_resend_verification_success(use_case, mock_user_repo, mock_token_repo, mock_email_sender):
    mock_user_repo.get_by_id.return_value = User(id=1, email="a@b.com", email_verified=False)

    result = await use_case.resend_verification(1, base_url="http://localhost")

    assert result is True
    mock_token_repo.create_token.assert_called_once()
    mock_email_sender.send_verification_email.assert_called_once()


async def test_resend_verification_already_verified(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, email="a@b.com", email_verified=True)

    result = await use_case.resend_verification(1)
    assert result is False


async def test_resend_verification_no_email(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, email=None, email_verified=False)

    result = await use_case.resend_verification(1)
    assert result is False


async def test_resend_verification_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None

    result = await use_case.resend_verification(1)
    assert result is False


# ================================================================
# request_email_change / confirm_email_change
# ================================================================

async def test_request_email_change_success(use_case, mock_user_repo, mock_token_repo, mock_email_sender):
    mock_user_repo.get_by_email.return_value = None

    await use_case.request_email_change(1, "new@mail.com", base_url="http://localhost")

    mock_token_repo.create_token.assert_called_once()
    assert mock_token_repo.create_token.call_args[1]["token_type"] == "email_change"
    assert mock_token_repo.create_token.call_args[1]["payload"] == "new@mail.com"
    mock_email_sender.send_email_change_verification.assert_called_once()


async def test_request_email_change_invalid_email(use_case):
    with pytest.raises(ValueError, match="invalid_email"):
        await use_case.request_email_change(1, "bad-email")


async def test_request_email_change_email_taken(use_case, mock_user_repo):
    mock_user_repo.get_by_email.return_value = User(id=2, email="taken@mail.com")

    with pytest.raises(ValueError, match="email_taken"):
        await use_case.request_email_change(1, "taken@mail.com")


async def test_request_email_change_same_user_email(use_case, mock_user_repo, mock_token_repo):
    """User can re-verify their own email (existing.id == user_id)."""
    mock_user_repo.get_by_email.return_value = User(id=1, email="same@mail.com")

    await use_case.request_email_change(1, "same@mail.com", base_url="http://localhost")
    mock_token_repo.create_token.assert_called_once()


async def test_confirm_email_change_success(use_case, mock_user_repo, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = {"user_id": 1, "payload": "new@mail.com"}
    mock_user_repo.get_by_id.return_value = User(id=1, email="old@mail.com")
    mock_user_repo.save_user.return_value = User(id=1, email="new@mail.com", email_verified=True)

    result = await use_case.confirm_email_change("valid-token")

    assert result is True
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email == "new@mail.com"
    assert saved.email_verified is True
    mock_token_repo.mark_used.assert_called_once()


async def test_confirm_email_change_invalid_token(use_case, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = None

    result = await use_case.confirm_email_change("bad-token")
    assert result is False


async def test_confirm_email_change_no_payload(use_case, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = {"user_id": 1, "payload": None}

    result = await use_case.confirm_email_change("token-no-payload")
    assert result is False


# ================================================================
# request_password_reset / reset_password
# ================================================================

async def test_request_password_reset_success(use_case, mock_user_repo, mock_token_repo, mock_email_sender):
    mock_user_repo.get_by_email.return_value = User(id=1, email="user@mail.com")

    await use_case.request_password_reset("user@mail.com", base_url="http://localhost")

    mock_token_repo.create_token.assert_called_once()
    assert mock_token_repo.create_token.call_args[1]["token_type"] == "password_reset"
    mock_email_sender.send_password_reset_email.assert_called_once()


async def test_request_password_reset_email_not_found(use_case, mock_user_repo, mock_token_repo):
    """Silent fail — no error raised, no token created."""
    mock_user_repo.get_by_email.return_value = None

    await use_case.request_password_reset("nobody@mail.com")

    mock_token_repo.create_token.assert_not_called()


async def test_reset_password_success(use_case, mock_user_repo, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = {"user_id": 1, "payload": None}
    mock_user_repo.get_by_id.return_value = User(id=1, email="user@mail.com", password_hash="old-hash")
    mock_user_repo.save_user.return_value = User(id=1)

    result = await use_case.reset_password("valid-token", "new_password_123")

    assert result is True
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.password_hash != "old-hash"
    mock_token_repo.mark_used.assert_called_once_with("valid-token")


async def test_reset_password_invalid_token(use_case, mock_token_repo):
    mock_token_repo.get_valid_token.return_value = None

    result = await use_case.reset_password("bad-token", "new_password")
    assert result is False


async def test_reset_password_no_token_repo(use_case_no_verification):
    result = await use_case_no_verification.reset_password("any-token", "password")
    assert result is False


# ================================================================
# get_user_profile / get_user_profile_by_tg_id
# ================================================================

async def test_get_user_profile(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, email="a@b.com")

    result = await use_case.get_user_profile(1)
    assert result.email == "a@b.com"
    mock_user_repo.get_by_id.assert_called_once_with(1)


async def test_get_user_profile_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None

    result = await use_case.get_user_profile(999)
    assert result is None


async def test_get_user_profile_by_tg_id(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(id=1, telegram_id=100)

    result = await use_case.get_user_profile_by_tg_id(100)
    assert result.telegram_id == 100


# ================================================================
# add_trigger_word (now uses user_id)
# ================================================================

async def test_add_trigger_word_success(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, keywords=[])

    await use_case.add_trigger_word(user_id=1, word="deadline")

    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.word == "deadline"
    assert kw.is_stop_word is False


async def test_add_trigger_word_duplicate_raises(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(
        id=1, keywords=[Keyword(word="deadline")]
    )

    with pytest.raises(ValueError, match="duplicate_keyword"):
        await use_case.add_trigger_word(user_id=1, word="Deadline")


# ================================================================
# add_stop_word (now uses user_id)
# ================================================================

async def test_add_stop_word_success(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, keywords=[])

    await use_case.add_stop_word(user_id=1, word="spam")

    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.word == "spam"
    assert kw.is_stop_word is True


async def test_add_stop_word_already_exists_raises(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(
        id=1, keywords=[Keyword(word="spam", is_stop_word=True)]
    )

    with pytest.raises(ValueError, match="already_exists"):
        await use_case.add_stop_word(user_id=1, word="spam")


async def test_convert_trigger_to_stop(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(
        id=1, keywords=[Keyword(word="promo", is_stop_word=False)]
    )

    await use_case.add_stop_word(user_id=1, word="promo")

    mock_user_repo.remove_keyword.assert_called_once_with(1, "promo")
    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.is_stop_word is True


# ================================================================
# set_email (now uses user_id, sets email_verified=False)
# ================================================================

async def test_set_email_valid(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, email_verified=True)

    await use_case.set_email(user_id=1, email="valid@mail.ru")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email == "valid@mail.ru"
    assert saved.email_verified is False


async def test_set_email_invalid_raises(use_case, mock_user_repo):
    with pytest.raises(ValueError, match="invalid_email"):
        await use_case.set_email(user_id=1, email="not-an-email")

    mock_user_repo.save_user.assert_not_called()


async def test_set_email_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None

    await use_case.set_email(user_id=1, email="valid@mail.ru")

    mock_user_repo.save_user.assert_not_called()


# ================================================================
# set_sensitivity (now uses user_id)
# ================================================================

async def test_set_sensitivity(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1)

    await use_case.set_sensitivity(user_id=1, level="high")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.ai_sensitivity == "high"


async def test_set_sensitivity_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None
    await use_case.set_sensitivity(user_id=1, level="high")
    mock_user_repo.save_user.assert_not_called()


# ================================================================
# toggle_dnd (now uses user_id)
# ================================================================

async def test_toggle_dnd_on(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, is_dnd=False)

    new_state, pending = await use_case.toggle_dnd(user_id=1)

    assert new_state is True
    assert pending == []
    mock_user_repo.set_dnd.assert_called_once_with(1, True)


async def test_toggle_dnd_off_with_pending(use_case, mock_user_repo, sample_pending):
    mock_user_repo.get_by_id.return_value = User(id=1, is_dnd=True)
    mock_user_repo.get_pending_notifications.return_value = [sample_pending]

    new_state, pending = await use_case.toggle_dnd(user_id=1)

    assert new_state is False
    assert len(pending) == 1
    mock_user_repo.clear_pending_notifications.assert_called_once_with(1)


async def test_toggle_dnd_off_no_pending(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = User(id=1, is_dnd=True)
    mock_user_repo.get_pending_notifications.return_value = []

    new_state, pending = await use_case.toggle_dnd(user_id=1)

    assert new_state is False
    assert pending == []


async def test_toggle_dnd_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None

    new_state, pending = await use_case.toggle_dnd(user_id=1)

    assert new_state is False
    assert pending == []


# ================================================================
# get_email_history
# ================================================================

async def test_get_email_history(use_case, mock_user_repo):
    mock_user_repo.get_email_history.return_value = [{"subject": "A"}, {"subject": "B"}]

    history = await use_case.get_email_history(user_id=1, limit=5)

    assert len(history) == 2
    mock_user_repo.get_email_history.assert_called_once_with(1, limit=5)


# ================================================================
# get_stats
# ================================================================

async def test_get_stats_with_cache(use_case, mock_user_repo, mock_cache_repo):
    stats = await use_case.get_stats(user_id=1)

    assert stats["total_processed"] == 5
    assert stats["important_count"] == 2
    assert stats["cache_total"] == 10


async def test_get_stats_no_cache_repo(mock_user_repo):
    uc = ManageUsersUseCase(user_repo=mock_user_repo, cache_repo=None)
    stats = await uc.get_stats(user_id=1)

    assert stats["cache_total"] == 0
