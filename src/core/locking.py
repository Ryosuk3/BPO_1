"""Модуль для защиты от Race Conditions через блокировки"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Callable, Awaitable
from src.core.config import config


class LockManager:
    """Менеджер блокировок для предотвращения race conditions"""
    
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()  # Блокировка для доступа к словарю
    
    def _get_lock_key(self, path: Path | str) -> str:
        """Получить ключ блокировки для пути"""
        return str(Path(path).resolve())
    
    async def _get_lock(self, path: Path | str) -> asyncio.Lock:
        """Получить или создать блокировку для пути"""
        key = self._get_lock_key(path)
        async with self._lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
    
    async def execute_locked(
        self,
        path: Path | str,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        Выполнить операцию с блокировкой пути.
        
        Args:
            path: Путь для блокировки
            operation: Асинхронная функция для выполнения
            
        Returns:
            Результат операции
        """
        lock = await self._get_lock(path)
        try:
            # Пытаемся захватить блокировку с таймаутом
            if await asyncio.wait_for(lock.acquire(), timeout=config.LOCK_TIMEOUT):
                try:
                    return await operation()
                finally:
                    lock.release()
            else:
                raise TimeoutError(
                    f"Не удалось заблокировать ресурс '{path}' в течение {config.LOCK_TIMEOUT} секунд"
                )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Ресурс '{path}' заблокирован другой операцией. Попробуйте позже."
            )
    
    async def execute_locked_multi(
        self,
        paths: list[Path | str],
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        Выполнить операцию с блокировкой нескольких путей (предотвращение дедлоков).
        
        Args:
            paths: Список путей для блокировки (блокируются в отсортированном порядке)
            operation: Асинхронная функция для выполнения
            
        Returns:
            Результат операции
        """
        # Сортируем пути для предотвращения дедлоков
        sorted_paths = sorted([self._get_lock_key(p) for p in paths])
        locks = []
        
        try:
            # Захватываем все блокировки в порядке сортировки
            for path_key in sorted_paths:
                lock = await self._get_lock(path_key)
                if await asyncio.wait_for(lock.acquire(), timeout=config.LOCK_TIMEOUT):
                    locks.append((path_key, lock))
                else:
                    # Освобождаем уже захваченные блокировки
                    for _, l in locks:
                        l.release()
                    raise TimeoutError(
                        f"Не удалось заблокировать все ресурсы в течение {config.LOCK_TIMEOUT} секунд"
                    )
            
            # Выполняем операцию
            return await operation()
        finally:
            # Освобождаем все блокировки в обратном порядке
            for _, lock in reversed(locks):
                lock.release()


# Глобальный экземпляр менеджера блокировок
lock_manager = LockManager()

