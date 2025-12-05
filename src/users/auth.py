"""Модуль аутентификации пользователей"""
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db
from src.core.models import User


def hash_password(password: str) -> str:
    """
    Хеширование пароля с использованием bcrypt.
    
    Args:
        password: Пароль в виде строки
        
    Returns:
        Хеш пароля в виде строки
    """
    # bcrypt требует bytes, ограничение 72 байта
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt)
    return password_hash.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Проверка пароля.
    
    Args:
        password: Пароль для проверки
        password_hash: Хеш пароля из БД
        
    Returns:
        True если пароль верный, иначе False
    """
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    hash_bytes = password_hash.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)


async def create_user(username: str, password: str) -> User:
    """
    Создание нового пользователя.
    
    Args:
        username: Имя пользователя
        password: Пароль
        
    Returns:
        Созданный пользователь
        
    Raises:
        ValueError: Если пользователь уже существует
    """
    async with db.session() as session:
        # Проверка существования пользователя (prepared statement через SQLAlchemy)
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError(f"Пользователь '{username}' уже существует")
        
        # Создание нового пользователя
        password_hash = hash_password(password)
        new_user = User(
            username=username,
            password_hash=password_hash
        )
        
        session.add(new_user)
        await session.flush()
        await session.refresh(new_user)
        
        return new_user


async def authenticate_user(username: str, password: str) -> User | None:
    """
    Аутентификация пользователя.
    
    Args:
        username: Имя пользователя
        password: Пароль
        
    Returns:
        Пользователь если аутентификация успешна, иначе None
    """
    async with db.session() as session:
        # Поиск пользователя (prepared statement через SQLAlchemy)
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user and verify_password(password, user.password_hash):
            return user
        
        return None


async def get_user_by_id(user_id: int) -> User | None:
    """
    Получить пользователя по ID.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Пользователь или None
    """
    async with db.session() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

