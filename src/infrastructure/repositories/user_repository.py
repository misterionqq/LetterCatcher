from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.core.entities import User, Keyword
from src.core.interfaces import IUserRepository
from src.infrastructure.database.models import UserModel, KeywordModel, ProcessedEmailModel

class SQLAlchemyUserRepository(IUserRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    def _to_entity(self, model: UserModel) -> User:
        keywords = [Keyword(word=k.word, is_stop_word=k.is_stop_word) for k in model.keywords]
        return User(
            telegram_id=model.telegram_id,
            email=model.email,
            ai_sensitivity=model.ai_sensitivity,
            is_dnd=model.is_dnd,
            keywords=keywords
        )

    async def get_by_telegram_id(self, tg_id: int) -> Optional[User]:
        async with self.session_factory() as session:
            stmt = select(UserModel).where(UserModel.telegram_id == tg_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> Optional[User]:
        async with self.session_factory() as session:
            stmt = select(UserModel).where(UserModel.email == email)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None

    async def save_user(self, user: User) -> None:
        async with self.session_factory() as session:
            stmt = select(UserModel).where(UserModel.telegram_id == user.telegram_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

            if not model:
                model = UserModel(telegram_id=user.telegram_id)
                session.add(model)
            
            model.email = user.email
            model.ai_sensitivity = user.ai_sensitivity
            model.is_dnd = user.is_dnd

            await session.commit()

    async def add_keyword(self, tg_id: int, keyword: Keyword) -> None:
        async with self.session_factory() as session:
            kw_model = KeywordModel(
                user_id=tg_id, 
                word=keyword.word.lower(),
                is_stop_word=keyword.is_stop_word
            )
            session.add(kw_model)
            await session.commit()

    async def remove_keyword(self, tg_id: int, word: str) -> None:
        async with self.session_factory() as session:
            stmt = select(KeywordModel).where(
                KeywordModel.user_id == tg_id,
                KeywordModel.word == word.lower()
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                await session.delete(model)
                await session.commit()

    async def set_dnd(self, tg_id: int, is_dnd: bool) -> None:
        async with self.session_factory() as session:
            stmt = select(UserModel).where(UserModel.telegram_id == tg_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                model.is_dnd = is_dnd
                await session.commit()

    async def is_email_processed(self, user_id: int, email_uid: str) -> bool:
        async with self.session_factory() as session:
            stmt = select(ProcessedEmailModel).where(
                ProcessedEmailModel.user_id == user_id,
                ProcessedEmailModel.email_uid == email_uid
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def mark_email_processed(self, user_id: int, email_uid: str) -> None:
        async with self.session_factory() as session:
            model = ProcessedEmailModel(user_id=user_id, email_uid=email_uid)
            session.add(model)
            await session.commit()