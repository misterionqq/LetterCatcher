from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.core.interfaces import ICacheRepository
from src.infrastructure.database.models import EmailCacheModel


class SQLAlchemyCacheRepository(ICacheRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def get_cached_result(self, text_hash: str) -> Optional[dict]:
        async with self.session_factory() as session:
            stmt = select(EmailCacheModel).where(EmailCacheModel.text_hash == text_hash)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                return {"is_important": model.is_important, "reason": model.reason}
            return None

    async def save_cached_result(self, text_hash: str, is_important: bool, reason: str) -> None:
        async with self.session_factory() as session:
            model = EmailCacheModel(text_hash=text_hash, is_important=is_important, reason=reason)
            session.add(model)
            await session.commit()

    async def get_total_cached(self) -> int:
        async with self.session_factory() as session:
            result = await session.scalar(select(func.count()).select_from(EmailCacheModel))
            return result or 0
