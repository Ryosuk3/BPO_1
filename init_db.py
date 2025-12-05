"""Скрипт для инициализации базы данных"""
import asyncio
from src.core.database import db, Base
from src.core.config import config


async def init_database():
    """Инициализация базы данных - создание таблиц"""
    print("Подключение к базе данных...")
    await db.connect()
    
    if not db._engine:
        print("Ошибка: не удалось подключиться к базе данных")
        return
    
    print("Создание таблиц...")
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("База данных инициализирована успешно!")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(init_database())

