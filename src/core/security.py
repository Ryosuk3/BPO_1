"""Модуль безопасности: защита от Path Traversal и другие проверки"""
import os
from pathlib import Path
from src.core.config import config


def resolve_secure_path(relative_path: str, base_path: Path = None) -> Path:
    """
    Безопасное разрешение пути с защитой от Path Traversal.
    
    Args:
        relative_path: Относительный путь от пользователя
        base_path: Базовый путь (по умолчанию SANDBOX_ROOT)
    
    Returns:
        Полный безопасный путь
        
    Raises:
        PermissionError: Если обнаружена попытка Path Traversal
        ValueError: Если путь содержит недопустимые символы
    """
    if base_path is None:
        base_path = config.SANDBOX_ROOT
    
    # Нормализация пути
    normalized = os.path.normpath(relative_path)
    
    # Проверка на недопустимые символы
    if os.path.sep in normalized and normalized.startswith(os.path.sep):
        normalized = normalized.lstrip(os.path.sep)
    
    # Разрешение полного пути
    full_path = (base_path / normalized).resolve()
    
    # Критическая проверка: путь должен начинаться с base_path
    base_resolved = base_path.resolve()
    if not str(full_path).startswith(str(base_resolved)):
        raise PermissionError(
            f"Path traversal detected: попытка выхода за пределы песочницы. "
            f"Запрошенный путь: {relative_path}"
        )
    
    return full_path


def validate_filename(filename: str) -> str:
    """
    Валидация имени файла.
    
    Args:
        filename: Имя файла
        
    Returns:
        Безопасное имя файла
        
    Raises:
        ValueError: Если имя файла недопустимо
    """
    # Получаем только базовое имя (без пути)
    safe_name = os.path.basename(filename)
    
    # Проверка длины
    if len(safe_name) > config.MAX_FILENAME_LENGTH:
        raise ValueError(f"Имя файла слишком длинное (максимум {config.MAX_FILENAME_LENGTH} символов)")
    
    # Проверка на недопустимые символы
    invalid_chars = set('<>:"|?*\\')
    if any(char in safe_name for char in invalid_chars):
        raise ValueError(f"Имя файла содержит недопустимые символы: {invalid_chars}")
    
    # Проверка на зарезервированные имена (Windows)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    if safe_name.upper() in reserved_names:
        raise ValueError(f"Имя файла '{safe_name}' зарезервировано системой")
    
    return safe_name

