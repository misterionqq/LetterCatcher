"""Tests for SmtpEmailSender — verify email construction and sending."""
import pytest
from unittest.mock import AsyncMock, patch

from src.infrastructure.smtp_service import SmtpEmailSender


@pytest.fixture
def sender():
    return SmtpEmailSender("smtp.test.com", 587, "bot@test.com", "secret")


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_verification_email(mock_send, sender):
    await sender.send_verification_email("user@example.com", "tok123", "https://app.com")
    mock_send.assert_awaited_once()

    msg = mock_send.call_args[0][0]
    assert msg["To"] == "user@example.com"
    assert msg["From"] == "bot@test.com"
    assert "Verify" in msg["Subject"]
    body = msg.get_payload()[0].get_payload(decode=True).decode()
    assert "https://app.com/api/v1/auth/verify-email?token=tok123" in body


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_password_reset_email(mock_send, sender):
    await sender.send_password_reset_email("user@example.com", "reset-tok", "https://app.com")
    mock_send.assert_awaited_once()

    msg = mock_send.call_args[0][0]
    body = msg.get_payload()[0].get_payload(decode=True).decode()
    assert "https://app.com/reset-password?token=reset-tok" in body
    assert "15 minutes" in body


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_link_code(mock_send, sender):
    await sender.send_link_code("user@example.com", "123456")
    mock_send.assert_awaited_once()

    msg = mock_send.call_args[0][0]
    assert "Telegram" in msg["Subject"]
    body = msg.get_payload()[0].get_payload(decode=True).decode()
    assert "123456" in body


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_email_change_verification(mock_send, sender):
    await sender.send_email_change_verification("new@example.com", "chg-tok", "https://app.com")
    mock_send.assert_awaited_once()

    msg = mock_send.call_args[0][0]
    body = msg.get_payload()[0].get_payload(decode=True).decode()
    assert "https://app.com/api/v1/auth/verify-email-change?token=chg-tok" in body


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_uses_correct_smtp_params(mock_send, sender):
    await sender.send_link_code("user@example.com", "000000")
    kwargs = mock_send.call_args[1]
    assert kwargs["hostname"] == "smtp.test.com"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "bot@test.com"
    assert kwargs["password"] == "secret"
    assert kwargs["start_tls"] is True


@pytest.mark.asyncio
@patch("src.infrastructure.smtp_service.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_failure_raises(mock_send, sender):
    mock_send.side_effect = Exception("SMTP connection refused")
    with pytest.raises(Exception, match="SMTP connection refused"):
        await sender.send_verification_email("user@example.com", "tok", "https://app.com")
