"""Модели базы данных"""
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from src.core.database import Base


class OperationType(str, Enum):
    """Типы операций"""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Связи
    files: Mapped[list["File"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    operations: Mapped[list["Operation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class File(Base):
    """Модель файла"""
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Связи
    owner: Mapped["User"] = relationship(back_populates="files")
    operations: Mapped[list["Operation"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class Operation(Base):
    """Модель операции"""
    __tablename__ = "operations"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    operation_type: Mapped[OperationType] = mapped_column(SQLEnum(OperationType), nullable=False)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Связи
    file: Mapped["File"] = relationship(back_populates="operations")
    user: Mapped["User"] = relationship(back_populates="operations")

