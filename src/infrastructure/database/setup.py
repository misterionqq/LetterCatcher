from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.infrastructure.config import DATABASE_URL
from src.infrastructure.database.models import Base

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)