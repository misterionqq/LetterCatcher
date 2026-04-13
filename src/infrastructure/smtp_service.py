import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib


class SmtpEmailSender:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    async def _send(self, to: str, subject: str, body_html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                start_tls=True,
            )
        except Exception as e:
            logging.error(f"SMTP send error to {to}: {e}")
            raise

    async def send_verification_email(self, to: str, token: str, base_url: str) -> None:
        link = f"{base_url}/api/v1/auth/verify-email?token={token}"
        html = (
            "<h2>LetterCatcher — Email Verification</h2>"
            "<p>Click the link below to verify your email address:</p>"
            f'<p><a href="{link}">{link}</a></p>'
            "<p>This link expires in 24 hours.</p>"
            "<p>If you did not register, ignore this email.</p>"
        )
        await self._send(to, "Verify your email — LetterCatcher", html)

    async def send_password_reset_email(self, to: str, token: str, base_url: str) -> None:
        link = f"{base_url}/reset-password?token={token}"
        html = (
            "<h2>LetterCatcher — Password Reset</h2>"
            "<p>Click the link below to reset your password:</p>"
            f'<p><a href="{link}">{link}</a></p>'
            "<p>This link expires in 15 minutes.</p>"
            "<p>If you did not request a password reset, ignore this email.</p>"
        )
        await self._send(to, "Password reset — LetterCatcher", html)

    async def send_email_change_verification(self, to: str, token: str, base_url: str) -> None:
        link = f"{base_url}/api/v1/auth/verify-email-change?token={token}"
        html = (
            "<h2>LetterCatcher — Email Change</h2>"
            "<p>Click the link below to confirm your new email address:</p>"
            f'<p><a href="{link}">{link}</a></p>'
            "<p>This link expires in 24 hours.</p>"
            "<p>If you did not request this change, ignore this email.</p>"
        )
        await self._send(to, "Confirm email change — LetterCatcher", html)
