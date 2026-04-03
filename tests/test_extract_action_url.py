from unittest.mock import AsyncMock
from src.use_cases.mail_scanner import MailScanner


def _make_scanner():
    return MailScanner(
        email_repo=AsyncMock(),
        user_repo=AsyncMock(),
        bot=AsyncMock(),
        ai_analyzer=AsyncMock(),
        cache_repo=AsyncMock(),
    )


def test_extracts_first_clean_url():
    scanner = _make_scanner()
    body = "Check this: https://example.com/action and more text"
    assert scanner._extract_action_url(body) == "https://example.com/action"


def test_skips_tracking_urls():
    scanner = _make_scanner()
    for noise in ["unsubscribe", "track", "pixel", "open.php", "click.php", "beacon"]:
        body = f"https://example.com/{noise}/link"
        assert scanner._extract_action_url(body) is None


def test_returns_clean_after_tracking():
    scanner = _make_scanner()
    body = "https://tracker.com/pixel/img https://portal.example.com/submit"
    assert scanner._extract_action_url(body) == "https://portal.example.com/submit"


def test_no_urls():
    scanner = _make_scanner()
    assert scanner._extract_action_url("just plain text") is None


def test_strips_trailing_punctuation():
    scanner = _make_scanner()
    body = "Visit https://example.com/page."
    assert scanner._extract_action_url(body) == "https://example.com/page"

    body2 = "(see https://example.com/page)"
    assert scanner._extract_action_url(body2) == "https://example.com/page"


def test_long_url_skipped():
    scanner = _make_scanner()
    long_url = "https://example.com/" + "a" * 200
    body = f"{long_url} https://short.com/ok"
    assert scanner._extract_action_url(body) == "https://short.com/ok"
