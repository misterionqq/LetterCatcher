import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete

from src.core.interfaces import IVerificationTokenRepository
from src.infrastructure.database.models import VerificationTokenModel


class SQLAlchemyTokenRepository(IVerificationTokenRepository):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def create_token(self, user_id: int, token_type: str, expires_at: datetime,
                           payload: str = None, token_value: str = None) -> str:
        token = token_value or secrets.token_urlsafe(32)
        async with self.session_factory() as session:
            model = VerificationTokenModel(
                user_id=user_id,
                token=token,
                token_type=token_type,
                payload=payload,
                expires_at=expires_at,
                used=False,
            )
            session.add(model)
            await session.commit()
        return token

    async def get_valid_token(self, token: str, token_type: str) -> Optional[dict]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(VerificationTokenModel).where(
                    VerificationTokenModel.token == token,
                    VerificationTokenModel.token_type == token_type,
                    VerificationTokenModel.used == False,
                    VerificationTokenModel.expires_at > datetime.utcnow(),
                )
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            return {"user_id": model.user_id, "payload": model.payload}

    async def mark_used(self, token: str) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(VerificationTokenModel).where(VerificationTokenModel.token == token)
            )
            model = result.scalar_one_or_none()
            if model:
                model.used = True
                await session.commit()

    async def cleanup_expired(self) -> None:
        async with self.session_factory() as session:
            await session.execute(
                delete(VerificationTokenModel).where(
                    VerificationTokenModel.expires_at < datetime.utcnow()
                )
            )
            await session.commit()
