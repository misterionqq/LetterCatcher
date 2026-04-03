import pytest
from unittest.mock import AsyncMock

from src.core.entities import User, Keyword, PendingNotification
from src.use_cases.manage_users import ManageUsersUseCase


@pytest.fixture
def use_case(mock_user_repo, mock_cache_repo):
    return ManageUsersUseCase(user_repo=mock_user_repo, cache_repo=mock_cache_repo)


# --- register_or_update_user ---

async def test_register_new_user(use_case, mock_user_repo):
    new_user = User(telegram_id=100, email="a@b.com")
    mock_user_repo.get_by_telegram_id.side_effect = [None, new_user]

    result = await use_case.register_or_update_user(tg_id=100, email="a@b.com")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.telegram_id == 100
    assert saved.email == "a@b.com"
    assert result == new_user


async def test_update_existing_email(use_case, mock_user_repo):
    existing = User(telegram_id=100, email="old@b.com")
    updated = User(telegram_id=100, email="new@b.com")
    mock_user_repo.get_by_telegram_id.side_effect = [existing, updated]

    result = await use_case.register_or_update_user(tg_id=100, email="new@b.com")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.email == "new@b.com"


# --- add_trigger_word ---

async def test_add_trigger_word_success(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100, keywords=[])

    await use_case.add_trigger_word(tg_id=100, word="deadline")

    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.word == "deadline"
    assert kw.is_stop_word is False


async def test_add_trigger_word_duplicate_raises(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(
        telegram_id=100, keywords=[Keyword(word="deadline")]
    )

    with pytest.raises(ValueError, match="duplicate_keyword"):
        await use_case.add_trigger_word(tg_id=100, word="Deadline")


# --- add_stop_word ---

async def test_add_stop_word_success(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100, keywords=[])

    await use_case.add_stop_word(tg_id=100, word="spam")

    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.word == "spam"
    assert kw.is_stop_word is True


async def test_add_stop_word_already_exists_raises(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(
        telegram_id=100, keywords=[Keyword(word="spam", is_stop_word=True)]
    )

    with pytest.raises(ValueError, match="already_exists"):
        await use_case.add_stop_word(tg_id=100, word="spam")


async def test_convert_trigger_to_stop(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(
        telegram_id=100, keywords=[Keyword(word="promo", is_stop_word=False)]
    )

    await use_case.add_stop_word(tg_id=100, word="promo")

    mock_user_repo.remove_keyword.assert_called_once_with(100, "promo")
    mock_user_repo.add_keyword.assert_called_once()
    kw = mock_user_repo.add_keyword.call_args[0][1]
    assert kw.is_stop_word is True


# --- set_email ---

async def test_set_email_valid(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100)

    await use_case.set_email(tg_id=100, email="valid@mail.ru")

    mock_user_repo.save_user.assert_called_once()


async def test_set_email_invalid_raises(use_case, mock_user_repo):
    with pytest.raises(ValueError, match="invalid_email"):
        await use_case.set_email(tg_id=100, email="not-an-email")

    mock_user_repo.save_user.assert_not_called()


async def test_set_email_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = None

    await use_case.set_email(tg_id=100, email="valid@mail.ru")

    mock_user_repo.save_user.assert_not_called()


# --- set_sensitivity ---

async def test_set_sensitivity(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100)

    await use_case.set_sensitivity(tg_id=100, level="high")

    mock_user_repo.save_user.assert_called_once()
    saved = mock_user_repo.save_user.call_args[0][0]
    assert saved.ai_sensitivity == "high"


async def test_set_sensitivity_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = None
    await use_case.set_sensitivity(tg_id=100, level="high")
    mock_user_repo.save_user.assert_not_called()


# --- toggle_dnd ---

async def test_toggle_dnd_on(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100, is_dnd=False)

    new_state, pending = await use_case.toggle_dnd(tg_id=100)

    assert new_state is True
    assert pending == []
    mock_user_repo.set_dnd.assert_called_once_with(100, True)


async def test_toggle_dnd_off_with_pending(use_case, mock_user_repo, sample_pending):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100, is_dnd=True)
    mock_user_repo.get_pending_notifications.return_value = [sample_pending]

    new_state, pending = await use_case.toggle_dnd(tg_id=100)

    assert new_state is False
    assert len(pending) == 1
    mock_user_repo.clear_pending_notifications.assert_called_once_with(100)


async def test_toggle_dnd_off_no_pending(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = User(telegram_id=100, is_dnd=True)
    mock_user_repo.get_pending_notifications.return_value = []

    new_state, pending = await use_case.toggle_dnd(tg_id=100)

    assert new_state is False
    assert pending == []


async def test_toggle_dnd_user_not_found(use_case, mock_user_repo):
    mock_user_repo.get_by_telegram_id.return_value = None

    new_state, pending = await use_case.toggle_dnd(tg_id=100)

    assert new_state is False
    assert pending == []


# --- get_stats ---

async def test_get_stats_with_cache(use_case, mock_user_repo, mock_cache_repo):
    stats = await use_case.get_stats(tg_id=100)

    assert stats["total_processed"] == 5
    assert stats["important_count"] == 2
    assert stats["cache_total"] == 10


async def test_get_stats_no_cache_repo(mock_user_repo):
    uc = ManageUsersUseCase(user_repo=mock_user_repo, cache_repo=None)
    stats = await uc.get_stats(tg_id=100)

    assert stats["cache_total"] == 0
