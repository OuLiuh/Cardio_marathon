import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_models():
    """
    Создаёт таблицы. Если RESET_DB=1 — сначала дропает все таблицы
    (удобно при смене схемы; на проде включать только осознанно).
    """
    reset = os.getenv("RESET_DB", "").lower() in ("1", "true", "yes")
    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency для FastAPI"""
    async with AsyncSessionLocal() as session:
        yield session
