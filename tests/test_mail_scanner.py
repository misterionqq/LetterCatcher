import pytest
from unittest.mock import patch, AsyncMock, call
from datetime import datetime

from src.core.entities import User, Keyword, EmailMessage
from src.use_cases.mail_scanner import MailScanner


ADMIN_TG_ID = 111222333


def _make_scanner(email_repo, user_repo, bot, ai_analyzer, cache_repo):
    return MailScanner(
        email_repo=email_repo,
        user_repo=user_repo,
        bot=bot,
        ai_analyzer=ai_analyzer,
        cache_repo=cache_repo,
    )


def _user(sensitivity="medium", is_dnd=False, keywords=None):
    return User(
        telegram_id=ADMIN_TG_ID,
        email="user@example.com",
        ai_sensitivity=sensitivity,
        is_dnd=is_dnd,
        keywords=keywords or [],
    )


def _email(uid="100", subject="Test", body="Body text", recipient="user@example.com"):
    return EmailMessage(
        uid=uid, sender="sender@co.com", subject=subject, body=body,
        date=datetime(2026, 4, 1), recipient_email=recipient,
    )


# ============= Routing =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_personal_mode_routes_to_admin(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    mock_email_repo.get_unread_emails.return_value = [_email()]
    mock_user_repo.get_by_telegram_id.return_value = _user()

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.get_by_telegram_id.assert_called_with(ADMIN_TG_ID)


@patch("src.use_cases.mail_scanner.APP_MODE", "centralized")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_centralized_routes_by_email(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    mock_email_repo.get_unread_emails.return_value = [_email(recipient="corp@co.com")]
    mock_user_repo.get_by_email.return_value = _user()

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.get_by_email.assert_called_with("corp@co.com")


@patch("src.use_cases.mail_scanner.APP_MODE", "centralized")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_centralized_unknown_recipient_skips(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    mock_email_repo.get_unread_emails.return_value = [_email(recipient="nobody@co.com")]
    mock_user_repo.get_by_email.return_value = None

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.mark_email_processed.assert_not_called()


# ============= Deduplication =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_already_processed_skipped(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    mock_email_repo.get_unread_emails.return_value = [_email()]
    mock_user_repo.get_by_telegram_id.return_value = _user()
    mock_user_repo.is_email_processed.return_value = True

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.mark_email_processed.assert_not_called()
    mock_bot.send_message.assert_not_called()


# ============= Stop words =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_stop_word_skips(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(keywords=[Keyword(word="реклама", is_stop_word=True)])
    mock_email_repo.get_unread_emails.return_value = [_email(body="Это реклама нового продукта")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.mark_email_processed.assert_called_once()
    args = mock_user_repo.mark_email_processed.call_args
    assert args.kwargs.get("is_important") is False or args[1].get("is_important") is False
    mock_bot.send_message.assert_not_called()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_stop_word_priority_over_trigger(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(keywords=[
        Keyword(word="urgent", is_stop_word=False),
        Keyword(word="spam", is_stop_word=True),
    ])
    mock_email_repo.get_unread_emails.return_value = [_email(body="urgent spam message")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_not_called()


# ============= Sensitivity: LOW =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_low_trigger_is_important(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="low", keywords=[Keyword(word="deadline")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="deadline is tomorrow")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_called_once()
    mock_ai_analyzer.analyze_urgency.assert_not_called()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_low_no_trigger_not_important(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="low", keywords=[Keyword(word="deadline")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="nothing special")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_not_called()
    mock_ai_analyzer.analyze_urgency.assert_not_called()


# ============= Sensitivity: MEDIUM =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_medium_trigger_ai_confirms(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="medium", keywords=[Keyword(word="urgent")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="urgent task")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_ai_analyzer.analyze_urgency.return_value = {"is_important": True, "reason": "Deadline"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_called_once()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_medium_trigger_ai_rejects(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="medium", keywords=[Keyword(word="urgent")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="urgent spam")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_ai_analyzer.analyze_urgency.return_value = {"is_important": False, "reason": "Spam"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_not_called()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_medium_no_trigger_skips_ai(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="medium", keywords=[Keyword(word="deadline")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="nothing here")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_ai_analyzer.analyze_urgency.assert_not_called()
    mock_bot.send_message.assert_not_called()


# ============= Sensitivity: HIGH =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_high_always_calls_ai(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="high", keywords=[])
    mock_email_repo.get_unread_emails.return_value = [_email(body="random text")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_ai_analyzer.analyze_urgency.return_value = {"is_important": True, "reason": "Test"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_ai_analyzer.analyze_urgency.assert_called_once()
    mock_bot.send_message.assert_called_once()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_high_ai_not_important(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="high", keywords=[])
    mock_email_repo.get_unread_emails.return_value = [_email(body="some text")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_ai_analyzer.analyze_urgency.return_value = {"is_important": False, "reason": "Not urgent"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_not_called()


# ============= DND =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_dnd_important_saves_pending(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="low", is_dnd=True, keywords=[Keyword(word="urgent")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="urgent task")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.add_pending_notification.assert_called_once()
    mock_bot.send_message.assert_not_called()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_no_dnd_important_sends(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="low", is_dnd=False, keywords=[Keyword(word="urgent")])
    mock_email_repo.get_unread_emails.return_value = [_email(body="urgent task")]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_bot.send_message.assert_called_once()
    mock_user_repo.add_pending_notification.assert_not_called()


# ============= Cache =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_cache_hit_skips_ai(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="high")
    mock_email_repo.get_unread_emails.return_value = [_email(body="cached body")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_cache_repo.get_cached_result.return_value = {"is_important": True, "reason": "Cached"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_ai_analyzer.analyze_urgency.assert_not_called()
    mock_bot.send_message.assert_called_once()


@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_cache_miss_calls_ai_and_saves(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="high")
    mock_email_repo.get_unread_emails.return_value = [_email(body="new body")]
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_cache_repo.get_cached_result.return_value = None
    mock_ai_analyzer.analyze_urgency.return_value = {"is_important": True, "reason": "New"}

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_ai_analyzer.analyze_urgency.assert_called_once()
    mock_cache_repo.save_cached_result.assert_called_once()


# ============= mark_email_processed always called =============

@patch("src.use_cases.mail_scanner.APP_MODE", "personal")
@patch("src.use_cases.mail_scanner.ADMIN_TG_ID", ADMIN_TG_ID)
async def test_mark_processed_always_called(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    user = _user(sensitivity="low", keywords=[])
    mock_email_repo.get_unread_emails.return_value = [_email()]
    mock_user_repo.get_by_telegram_id.return_value = user

    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)
    await scanner._check_mail_iteration()

    mock_user_repo.mark_email_processed.assert_called_once()


# ============= Graceful shutdown =============

async def test_stop_sets_event(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo):
    scanner = _make_scanner(mock_email_repo, mock_user_repo, mock_bot, mock_ai_analyzer, mock_cache_repo)

    assert not scanner._stop_event.is_set()
    assert not scanner.is_running

    scanner.is_running = True
    scanner.stop()

    assert scanner._stop_event.is_set()
    assert not scanner.is_running
