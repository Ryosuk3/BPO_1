"""Конфигурация приложения"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Класс конфигурации приложения"""
    
    # База данных
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://filemanager:secure_password_123@localhost:5432/filemanager_db"
    )
    
    # Песочница
    SANDBOX_ROOT: Path = Path(os.getenv("SANDBOX_ROOT", "./sandbox")).resolve()
    
    # Ограничения безопасности
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 104857600))  # 100 MB
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", 20971520))  # 20 MB
    MAX_FILENAME_LENGTH: int = 255
    
    # ZIP ограничения
    ZIP_MAX_TOTAL_SIZE: int = int(os.getenv("ZIP_MAX_TOTAL_SIZE", 2147483648))  # 2 GB
    ZIP_MAX_RATIO: float = float(os.getenv("ZIP_MAX_RATIO", 100.0))
    ZIP_MAX_FILES: int = int(os.getenv("ZIP_MAX_FILES", 1000))
    ZIP_MAX_RECURSION_DEPTH: int = 5
    
    # Блокировки
    LOCK_TIMEOUT: int = 5  # секунды


config = Config()

