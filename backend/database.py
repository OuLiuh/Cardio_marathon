import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base

from config import DATABASE_URL

# Создаем движок
engine = create_async_engine(DATABASE_URL, echo=True)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_models():
    """
    Эта функция создает таблицы в БД.
    В продакшене обычно используют Alembic (миграции), 
    но для старта проекта create_all — идеальный вариант.
    """
    async with engine.begin() as conn:
        # run_sync позволяет выполнять синхронные методы (create_all) в асинхронном контексте
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency для FastAPI"""
    async with AsyncSessionLocal() as session:
        yield session