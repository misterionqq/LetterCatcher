from src.use_cases.mail_scanner import _format_notification


def test_basic_structure():
    result = _format_notification(
        sender="John", subject="Hello", body_snippet="Some text",
        ai_reason="Important meeting",
    )
    assert "ВАЖНОЕ ПИСЬМО" in result
    assert "John" in result
    assert "Hello" in result
    assert "Some text" in result
    assert "Important meeting" in result


def test_pending_prefix():
    result = _format_notification(
        sender="John", subject="Hello", body_snippet="text",
        ai_reason="reason", pending=True,
    )
    assert "ОТЛОЖЕННОЕ УВЕДОМЛЕНИЕ" in result
    assert "ВАЖНОЕ ПИСЬМО" not in result


def test_with_triggered_word():
    result = _format_notification(
        sender="A", subject="B", body_snippet="C",
        ai_reason="D", triggered_word="deadline",
    )
    assert "Триггер" in result
    assert "<code>deadline</code>" in result


def test_without_triggered_word():
    result = _format_notification(
        sender="A", subject="B", body_snippet="C",
        ai_reason="D", triggered_word=None,
    )
    assert "Триггер" not in result


def test_with_action_url():
    result = _format_notification(
        sender="A", subject="B", body_snippet="C",
        ai_reason="D", action_url="https://example.com",
    )
    assert "Ссылка" in result
    assert 'href="https://example.com"' in result


def test_without_action_url():
    result = _format_notification(
        sender="A", subject="B", body_snippet="C",
        ai_reason="D", action_url=None,
    )
    assert "Ссылка" not in result


def test_html_escaping():
    result = _format_notification(
        sender="<script>alert(1)</script>",
        subject="Test & <b>bold</b>",
        body_snippet="<img src=x>",
        ai_reason="safe",
    )
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&amp;" in result
