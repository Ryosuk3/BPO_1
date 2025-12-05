"""Модуль логирования операций пользователей"""
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db
from src.core.models import Operation, User, File


async def get_user_operations(
    user_id: int,
    limit: int = 100,
) -> list[Operation]:
    """
    Получить операции пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество записей
        
    Returns:
        Список операций
    """
    async with db.session() as session:
        stmt = (
            select(Operation)
            .where(Operation.user_id == user_id)
            .order_by(desc(Operation.timestamp))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_file_operations(
    file_id: int,
    limit: int = 100,
) -> list[Operation]:
    """
    Получить операции с файлом.
    
    Args:
        file_id: ID файла
        limit: Максимальное количество записей
        
    Returns:
        Список операций
    """
    async with db.session() as session:
        stmt = (
            select(Operation)
            .where(Operation.file_id == file_id)
            .order_by(desc(Operation.timestamp))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

