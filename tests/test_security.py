"""Tests for JWT token creation and verification."""
import pytest
from unittest.mock import patch
from jose import jwt

from src.presentation.api.security import create_access_token, get_current_user_id
from src.infrastructure.config import JWT_SECRET_KEY, JWT_ALGORITHM


class _FakeCredentials:
    def __init__(self, token: str):
        self.credentials = token


def test_create_token_contains_user_id():
    token = create_access_token(user_id=42)
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "42"


def test_create_token_has_expiration():
    token = create_access_token(user_id=1)
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert "exp" in payload


def test_get_current_user_id_valid_token():
    token = create_access_token(user_id=99)
    creds = _FakeCredentials(token)
    assert get_current_user_id(creds) == 99


def test_get_current_user_id_invalid_token():
    from fastapi import HTTPException
    creds = _FakeCredentials("invalid.jwt.token")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(creds)
    assert exc_info.value.status_code == 401


def test_get_current_user_id_expired_token():
    from fastapi import HTTPException
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    creds = _FakeCredentials(token)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(creds)
    assert exc_info.value.status_code == 401


def test_get_current_user_id_wrong_secret():
    from fastapi import HTTPException
    payload = {"sub": "1", "exp": 9999999999}
    token = jwt.encode(payload, "wrong-secret", algorithm=JWT_ALGORITHM)
    creds = _FakeCredentials(token)
    with pytest.raises(HTTPException):
        get_current_user_id(creds)


def test_get_current_user_id_missing_sub():
    from fastapi import HTTPException
    payload = {"exp": 9999999999}  # no "sub"
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    creds = _FakeCredentials(token)
    with pytest.raises(HTTPException):
        get_current_user_id(creds)
