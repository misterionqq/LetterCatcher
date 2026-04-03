import pytest
from sqlalchemy.exc import IntegrityError

from src.infrastructure.repositories.cache_repository import SQLAlchemyCacheRepository


@pytest.fixture
def repo(db_session_factory):
    return SQLAlchemyCacheRepository(session_factory=db_session_factory)


async def test_save_and_get(repo):
    await repo.save_cached_result("hash1", is_important=True, reason="Deadline")
    result = await repo.get_cached_result("hash1")
    assert result is not None
    assert result["is_important"] is True
    assert result["reason"] == "Deadline"


async def test_cache_miss(repo):
    assert await repo.get_cached_result("nonexistent") is None


async def test_get_total_cached(repo):
    await repo.save_cached_result("h1", True, "r1")
    await repo.save_cached_result("h2", False, "r2")
    await repo.save_cached_result("h3", True, "r3")

    assert await repo.get_total_cached() == 3


async def test_duplicate_hash_raises(repo):
    await repo.save_cached_result("dup", True, "first")
    with pytest.raises(IntegrityError):
        await repo.save_cached_result("dup", False, "second")
