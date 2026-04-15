import pytest
from datetime import datetime, timedelta

from src.core.entities import User
from src.infrastructure.repositories.token_repository import SQLAlchemyTokenRepository
from src.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


@pytest.fixture
def user_repo(db_session_factory):
    return SQLAlchemyUserRepository(session_factory=db_session_factory)


@pytest.fixture
def token_repo(db_session_factory):
    return SQLAlchemyTokenRepository(session_factory=db_session_factory)


async def _create_user(user_repo) -> User:
    return await user_repo.save_user(User(email="test@mail.com"))


# --- create & get ---

async def test_create_and_get_valid_token(user_repo, token_repo):
    user = await _create_user(user_repo)
    token = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    assert isinstance(token, str)
    assert len(token) > 20

    result = await token_repo.get_valid_token(token, "email_verify")
    assert result is not None
    assert result["user_id"] == user.id
    assert result["payload"] is None


async def test_create_token_with_payload(user_repo, token_repo):
    user = await _create_user(user_repo)
    token = await token_repo.create_token(
        user_id=user.id, token_type="email_change",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        payload="new@email.com",
    )

    result = await token_repo.get_valid_token(token, "email_change")
    assert result["payload"] == "new@email.com"


# --- wrong token type ---

async def test_get_token_wrong_type(user_repo, token_repo):
    user = await _create_user(user_repo)
    token = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    result = await token_repo.get_valid_token(token, "password_reset")
    assert result is None


# --- nonexistent token ---

async def test_get_nonexistent_token(token_repo):
    result = await token_repo.get_valid_token("no-such-token", "email_verify")
    assert result is None


# --- expired token ---

async def test_expired_token_not_returned(user_repo, token_repo):
    user = await _create_user(user_repo)
    token = await token_repo.create_token(
        user_id=user.id, token_type="password_reset",
        expires_at=datetime.utcnow() - timedelta(seconds=1),  # already expired
    )

    result = await token_repo.get_valid_token(token, "password_reset")
    assert result is None


# --- mark_used ---

async def test_mark_used_prevents_reuse(user_repo, token_repo):
    user = await _create_user(user_repo)
    token = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    assert await token_repo.get_valid_token(token, "email_verify") is not None

    await token_repo.mark_used(token)

    assert await token_repo.get_valid_token(token, "email_verify") is None


# --- cleanup_expired ---

async def test_cleanup_expired(user_repo, token_repo):
    user = await _create_user(user_repo)

    # Create one expired and one valid token
    expired = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    valid = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    await token_repo.cleanup_expired()

    # Expired token should be gone
    assert await token_repo.get_valid_token(expired, "email_verify") is None
    # Valid token should still work
    assert await token_repo.get_valid_token(valid, "email_verify") is not None


# --- uniqueness ---

async def test_multiple_tokens_same_user(user_repo, token_repo):
    user = await _create_user(user_repo)
    t1 = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    t2 = await token_repo.create_token(
        user_id=user.id, token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    assert t1 != t2
    assert await token_repo.get_valid_token(t1, "email_verify") is not None
    assert await token_repo.get_valid_token(t2, "email_verify") is not None
