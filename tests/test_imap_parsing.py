"""Tests for ImapEmailRepository pure parsing/extraction methods.

These tests cover HTML sanitization, link extraction, header decoding,
body parsing, attachment extraction, and recipient determination —
all without needing a real IMAP connection.
"""
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from unittest.mock import patch

import pytest

from src.infrastructure.imap_client import (
    ImapEmailRepository,
    _sanitize_email_html,
)


@pytest.fixture
def repo():
    return ImapEmailRepository("imap.test.com", "bot@test.com", "pass")


# ── _sanitize_email_html ──────────────────────────────────────────


def test_sanitize_strips_script_tags():
    html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
    result = _sanitize_email_html(html)
    assert "<script>" not in result
    assert "alert" not in result
    assert "<p>Hello</p>" in result
    assert "<p>World</p>" in result


def test_sanitize_keeps_safe_tags():
    html = '<h1>Title</h1><p>Text <b>bold</b> <a href="https://x.com">link</a></p>'
    result = _sanitize_email_html(html)
    assert "<h1>" in result
    assert "<b>bold</b>" in result
    assert 'href="https://x.com"' in result


def test_sanitize_removes_onclick():
    html = '<p onclick="alert(1)">click me</p>'
    result = _sanitize_email_html(html)
    assert "onclick" not in result
    assert "<p>" in result


def test_sanitize_empty_input():
    assert _sanitize_email_html("") == ""
    assert _sanitize_email_html(None) is None


def test_sanitize_preserves_table():
    html = '<table border="1"><tr><td>cell</td></tr></table>'
    result = _sanitize_email_html(html)
    assert "<table" in result
    assert "<td>" in result


def test_sanitize_strips_comments():
    html = "<p>visible</p><!-- hidden comment --><p>also visible</p>"
    result = _sanitize_email_html(html)
    assert "hidden comment" not in result
    assert "visible" in result


@patch("src.infrastructure.imap_client.SANITIZE_HTML", False)
def test_sanitize_disabled():
    html = '<script>alert("xss")</script>'
    assert _sanitize_email_html(html) == html


# ── _decode_header_part ───────────────────────────────────────────


def test_decode_plain_ascii(repo):
    assert repo._decode_header_part("Hello World") == "Hello World"


def test_decode_utf8_encoded(repo):
    encoded = "=?utf-8?B?0J/RgNC40LLQtdGC?="  # "Привет" in base64
    result = repo._decode_header_part(encoded)
    assert result == "Привет"


def test_decode_mixed_parts(repo):
    encoded = "=?utf-8?B?0J/RgNC40LLQtdGC?= World"
    result = repo._decode_header_part(encoded)
    assert "Привет" in result
    assert "World" in result


def test_decode_empty_subject(repo):
    assert repo._decode_header_part("") == ""


# ── _extract_links ────────────────────────────────────────────────


def test_extract_links_from_html(repo):
    html = '<a href="https://example.com/page">Link</a>'
    links = repo._extract_links(html, "")
    assert "https://example.com/page" in links


def test_extract_links_dedup(repo):
    html = (
        '<a href="https://example.com">A</a>'
        '<a href="https://example.com">B</a>'
    )
    links = repo._extract_links(html, "")
    assert links.count("https://example.com") == 1


def test_extract_links_filters_noise(repo):
    html = (
        '<a href="https://example.com/unsubscribe">Unsub</a>'
        '<a href="https://example.com/track?id=1">Track</a>'
        '<a href="https://real.com/page">Real</a>'
    )
    links = repo._extract_links(html, "")
    assert "https://real.com/page" in links
    assert all("unsubscribe" not in l for l in links)
    assert all("track" not in l for l in links)


def test_extract_links_from_plain_text(repo):
    text = "Check out https://example.com/doc and let me know"
    links = repo._extract_links("", text)
    assert "https://example.com/doc" in links


def test_extract_links_skips_short_urls(repo):
    html = '<a href="http://x">X</a>'
    links = repo._extract_links(html, "")
    assert len(links) == 0


def test_extract_links_filters_mailto(repo):
    html = '<a href="mailto:test@example.com">Email</a>'
    links = repo._extract_links(html, "")
    assert len(links) == 0


def test_extract_links_strips_trailing_punctuation(repo):
    text = "Visit https://example.com/page. Then continue."
    links = repo._extract_links("", text)
    assert links[0] == "https://example.com/page"


# ── _parse_body ───────────────────────────────────────────────────


def test_parse_body_plain_text(repo):
    msg = MIMEText("Hello plain text", "plain", "utf-8")
    text, html = repo._parse_body(msg)
    assert "Hello plain text" in text
    assert html == ""


def test_parse_body_html_only(repo):
    msg = MIMEText("<p>Hello HTML</p>", "html", "utf-8")
    text, html = repo._parse_body(msg)
    assert "Hello HTML" in text  # extracted from HTML
    assert "<p>" in html or "Hello HTML" in html


def test_parse_body_multipart(repo):
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("Plain version", "plain", "utf-8"))
    msg.attach(MIMEText("<p>HTML version</p>", "html", "utf-8"))
    text, html = repo._parse_body(msg)
    assert "Plain version" in text
    assert "HTML version" in html


def test_parse_body_empty(repo):
    msg = MIMEText("", "plain", "utf-8")
    text, html = repo._parse_body(msg)
    assert "Пустое письмо" in text


def test_parse_body_skips_attachments(repo):
    msg = MIMEMultipart("mixed")
    msg.attach(MIMEText("Body text", "plain", "utf-8"))
    att = MIMEBase("application", "pdf")
    att.set_payload(b"fake pdf content")
    att.add_header("Content-Disposition", "attachment", filename="doc.pdf")
    msg.attach(att)
    text, html = repo._parse_body(msg)
    assert "Body text" in text


# ── _extract_attachments ──────────────────────────────────────────


def test_extract_attachments(repo):
    msg = MIMEMultipart("mixed")
    msg.attach(MIMEText("Body", "plain", "utf-8"))
    att = MIMEBase("application", "pdf")
    content = b"fake pdf content here"
    att.set_payload(content)
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename="report.pdf")
    msg.attach(att)
    attachments = repo._extract_attachments(msg)
    assert len(attachments) == 1
    assert attachments[0]["name"] == "report.pdf"
    assert attachments[0]["content_type"] == "application/pdf"
    assert attachments[0]["size"] == len(content)


def test_extract_attachments_none(repo):
    msg = MIMEText("Just text", "plain", "utf-8")
    assert repo._extract_attachments(msg) == []


def test_extract_attachments_no_filename(repo):
    msg = MIMEMultipart("mixed")
    msg.attach(MIMEText("Body", "plain"))
    att = MIMEBase("application", "octet-stream")
    att.set_payload(b"data")
    att.add_header("Content-Disposition", "attachment")  # no filename
    msg.attach(att)
    assert repo._extract_attachments(msg) == []


def test_extract_multiple_attachments(repo):
    msg = MIMEMultipart("mixed")
    msg.attach(MIMEText("Body", "plain"))
    for name in ["a.txt", "b.png"]:
        att = MIMEBase("application", "octet-stream")
        att.set_payload(b"x")
        encoders.encode_base64(att)
        att.add_header("Content-Disposition", "attachment", filename=name)
        msg.attach(att)
    assert len(repo._extract_attachments(msg)) == 2


# ── _determine_recipient ─────────────────────────────────────────


@patch("src.infrastructure.imap_client.APP_MODE", "personal")
def test_recipient_personal_mode(repo):
    msg = MIMEText("text")
    assert repo._determine_recipient(msg, "text") == "bot@test.com"


@patch("src.infrastructure.imap_client.APP_MODE", "centralized")
def test_recipient_centralized_to_header(repo):
    msg = MIMEText("text")
    msg["To"] = "worker@company.com"
    result = repo._determine_recipient(msg, "text")
    assert result == "worker@company.com"


@patch("src.infrastructure.imap_client.APP_MODE", "centralized")
def test_recipient_centralized_forwarded_header(repo):
    msg = MIMEText("text")
    msg["To"] = "bot@test.com"  # same as service mailbox
    msg["X-Forwarded-To"] = "real.user@company.com"
    result = repo._determine_recipient(msg, "text")
    assert result == "real.user@company.com"


@patch("src.infrastructure.imap_client.APP_MODE", "centralized")
def test_recipient_centralized_fallback_to_body(repo):
    msg = MIMEText("text")
    msg["To"] = "bot@test.com"
    body = "Forwarded message\nTo: original@company.com\nSubject: Hello"
    result = repo._determine_recipient(msg, body)
    assert result == "original@company.com"


@patch("src.infrastructure.imap_client.APP_MODE", "centralized")
def test_recipient_centralized_ultimate_fallback(repo):
    msg = MIMEText("text")
    msg["To"] = "bot@test.com"
    result = repo._determine_recipient(msg, "no email here")
    assert result == "bot@test.com"
