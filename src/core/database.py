"""Модуль для работы с базой данных"""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from asyncio import current_task
from sqlalchemy.ext.asyncio import async_scoped_session
from contextvars import ContextVar

from src.core.config import config

# Базовый класс для моделей
Base = declarative_base()

# Контекстная переменная для текущей сессии
_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "current_session", default=None
)


class Database:
    """Класс для управления подключением к БД"""
    
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker | None = None
    
    async def connect(self):
        """Подключение к базе данных"""
        if self._engine is None:
            self._engine = create_async_engine(
                config.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
            )
        if self._session_maker is None:
            self._session_maker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
    
    async def disconnect(self):
        """Отключение от базы данных"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
    
    @asynccontextmanager
    async def session(self):
        """Контекстный менеджер для сессии БД"""
        if self._session_maker is None:
            raise RuntimeError("Database not connected")
        
        scoped_session = async_scoped_session(
            session_factory=self._session_maker,
            scopefunc=current_task,
        )
        
        async with scoped_session() as session:
            token = _current_session.set(session)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                _current_session.reset(token)
                await scoped_session.remove()
    
    def get_current_session(self) -> AsyncSession | None:
        """Получить текущую сессию из контекста"""
        return _current_session.get()


# Глобальный экземпляр
db = Database()

