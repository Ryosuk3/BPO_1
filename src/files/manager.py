"""Менеджер файлов с безопасными операциями"""
import os
import shutil
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db
from src.core.models import File, User, Operation, OperationType
from src.core.security import resolve_secure_path, validate_filename
from src.core.locking import lock_manager
from src.core.config import config
from src.core.serialization import safe_load_json, safe_dump_json, safe_load_xml, safe_dump_xml
from src.core.archive import safe_create_zip, safe_extract_zip, ArchiveSecurityError


class FileManager:
    """Менеджер для работы с файлами"""
    
    def __init__(self):
        # Создаем корневую директорию песочницы если её нет
        config.SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    
    async def create_file(
        self,
        relative_path: str,
        user_id: int,
        content: str = "",
    ) -> File:
        """
        Создание файла.
        
        Args:
            relative_path: Относительный путь к файлу
            user_id: ID пользователя
            content: Начальное содержимое файла
            
        Returns:
            Модель созданного файла
        """
        # Валидация и разрешение пути
        full_path = resolve_secure_path(relative_path)
        validate_filename(full_path.name)
        
        # Проверка размера содержимого
        if len(content.encode('utf-8')) > config.MAX_UPLOAD_SIZE:
            raise ValueError(
                f"Размер содержимого превышает максимальный ({config.MAX_UPLOAD_SIZE} байт)"
            )
        
        async def _create():
            # Проверка существования
            if full_path.exists():
                raise FileExistsError(f"Файл '{relative_path}' уже существует")
            
            # Создание родительских директорий
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Создание файла
            full_path.write_text(content, encoding='utf-8')
            file_size = full_path.stat().st_size
            
            # Сохранение в БД
            async with db.session() as session:
                # Получаем пользователя
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    raise ValueError(f"Пользователь с ID {user_id} не найден")
                
                # Создаем запись о файле
                file_record = File(
                    filename=full_path.name,
                    size=file_size,
                    location=relative_path,
                    owner_id=user_id
                )
                session.add(file_record)
                await session.flush()
                
                # Логируем операцию
                operation = Operation(
                    operation_type=OperationType.CREATE,
                    file_id=file_record.id,
                    user_id=user_id
                )
                session.add(operation)
                await session.commit()
                await session.refresh(file_record)
                
                return file_record
        
        return await lock_manager.execute_locked(full_path, _create)
    
    async def read_file(
        self,
        relative_path: str,
        format_type: str = "text",
    ) -> str:
        """
        Чтение файла.
        
        Args:
            relative_path: Относительный путь к файлу
            format_type: Тип формата (text, json, xml)
            
        Returns:
            Содержимое файла
        """
        full_path = resolve_secure_path(relative_path)
        
        if not full_path.exists() or not full_path.is_file():
            raise FileNotFoundError(f"Файл '{relative_path}' не найден")
        
        # Проверка размера файла
        file_size = full_path.stat().st_size
        if file_size > config.MAX_FILE_SIZE:
            raise ValueError(
                f"Размер файла ({file_size} байт) превышает максимальный ({config.MAX_FILE_SIZE} байт)"
            )
        
        content = full_path.read_text(encoding='utf-8')
        
        # Обработка форматов
        if format_type == "json":
            try:
                data = safe_load_json(content)
                return safe_dump_json(data, indent=2)
            except ValueError as e:
                raise ValueError(f"Ошибка парсинга JSON: {e}")
        elif format_type == "xml":
            try:
                element = safe_load_xml(content)
                return safe_dump_xml(element).decode('utf-8')
            except ValueError as e:
                raise ValueError(f"Ошибка парсинга XML: {e}")
        
        return content
    
    async def write_file(
        self,
        relative_path: str,
        content: str,
        user_id: int,
        append: bool = False,
    ) -> File:
        """
        Запись в файл.
        
        Args:
            relative_path: Относительный путь к файлу
            content: Содержимое для записи
            user_id: ID пользователя
            append: Добавлять в конец или перезаписывать
            
        Returns:
            Модель файла
        """
        full_path = resolve_secure_path(relative_path)
        
        # Проверка размера
        content_size = len(content.encode('utf-8'))
        if content_size > config.MAX_UPLOAD_SIZE:
            raise ValueError(
                f"Размер содержимого превышает максимальный ({config.MAX_UPLOAD_SIZE} байт)"
            )
        
        async def _write():
            if not full_path.exists():
                raise FileNotFoundError(f"Файл '{relative_path}' не найден")
            
            # Безопасная запись через временный файл
            temp_path = full_path.with_suffix(full_path.suffix + '.tmp')
            
            try:
                if append:
                    existing_content = full_path.read_text(encoding='utf-8')
                    new_content = existing_content + content
                else:
                    new_content = content
                
                temp_path.write_text(new_content, encoding='utf-8')
                
                # Атомарная замена
                temp_path.replace(full_path)
                
                file_size = full_path.stat().st_size
                
                # Обновление в БД
                async with db.session() as session:
                    stmt = select(File).where(File.location == relative_path)
                    result = await session.execute(stmt)
                    file_record = result.scalar_one_or_none()
                    
                    if file_record:
                        file_record.size = file_size
                    else:
                        # Создаем новую запись если её нет
                        file_record = File(
                            filename=full_path.name,
                            size=file_size,
                            location=relative_path,
                            owner_id=user_id
                        )
                        session.add(file_record)
                    
                    await session.flush()
                    
                    # Логируем операцию
                    operation = Operation(
                        operation_type=OperationType.MODIFY,
                        file_id=file_record.id,
                        user_id=user_id
                    )
                    session.add(operation)
                    await session.commit()
                    await session.refresh(file_record)
                    
                    return file_record
            except Exception:
                if temp_path.exists():
                    temp_path.unlink()
                raise
        
        return await lock_manager.execute_locked(full_path, _write)
    
    async def delete_file(
        self,
        relative_path: str,
        user_id: int,
    ) -> None:
        """
        Удаление файла.
        
        Args:
            relative_path: Относительный путь к файлу
            user_id: ID пользователя
        """
        full_path = resolve_secure_path(relative_path)
        
        async def _delete():
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"Файл '{relative_path}' не найден")
            
            # Удаление файла
            full_path.unlink()
            
            # Обновление БД
            async with db.session() as session:
                stmt = select(File).where(File.location == relative_path)
                result = await session.execute(stmt)
                file_record = result.scalar_one_or_none()
                
                if file_record:
                    # Логируем операцию
                    operation = Operation(
                        operation_type=OperationType.DELETE,
                        file_id=file_record.id,
                        user_id=user_id
                    )
                    session.add(operation)
                    await session.commit()
        
        await lock_manager.execute_locked(full_path, _delete)
    
    async def create_directory(
        self,
        relative_path: str,
    ) -> None:
        """
        Создание директории.
        
        Args:
            relative_path: Относительный путь к директории
        """
        full_path = resolve_secure_path(relative_path)
        
        async def _create():
            if full_path.exists():
                raise FileExistsError(f"Директория '{relative_path}' уже существует")
            
            full_path.mkdir(parents=True, exist_ok=True)
        
        await lock_manager.execute_locked(full_path, _create)
    
    async def delete_directory(
        self,
        relative_path: str,
        recursive: bool = False,
    ) -> None:
        """
        Удаление директории.
        
        Args:
            relative_path: Относительный путь к директории
            recursive: Рекурсивное удаление
        """
        full_path = resolve_secure_path(relative_path)
        
        async def _delete():
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"Директория '{relative_path}' не найдена")
            
            if recursive:
                shutil.rmtree(full_path)
            else:
                if any(full_path.iterdir()):
                    raise ValueError(
                        f"Директория '{relative_path}' не пуста. Используйте флаг -r для рекурсивного удаления"
                    )
                full_path.rmdir()
        
        await lock_manager.execute_locked(full_path, _delete)
    
    async def move(
        self,
        source: str,
        destination: str,
    ) -> None:
        """
        Перемещение файла или директории.
        
        Args:
            source: Исходный путь
            destination: Путь назначения
        """
        source_path = resolve_secure_path(source)
        dest_path = resolve_secure_path(destination)
        
        async def _move():
            if not source_path.exists():
                raise FileNotFoundError(f"Источник '{source}' не найден")
            
            if dest_path.exists():
                raise FileExistsError(f"Путь назначения '{destination}' уже существует")
            
            # Создаем родительские директории
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Безопасное перемещение
            shutil.move(str(source_path), str(dest_path))
        
        await lock_manager.execute_locked_multi([source_path, dest_path], _move)
    
    async def list_directory(
        self,
        relative_path: str = ".",
    ) -> list[dict]:
        """
        Список содержимого директории.
        
        Args:
            relative_path: Относительный путь к директории
            
        Returns:
            Список словарей с информацией о файлах и директориях
        """
        full_path = resolve_secure_path(relative_path)
        
        if not full_path.exists() or not full_path.is_dir():
            raise NotADirectoryError(f"Директория '{relative_path}' не найдена")
        
        items = []
        for item in full_path.iterdir():
            if item.is_dir():
                items.append({
                    "name": item.name,
                    "type": "directory",
                    "size": None,
                })
            else:
                items.append({
                    "name": item.name,
                    "type": "file",
                    "size": item.stat().st_size,
                })
        
        return sorted(items, key=lambda x: (x["type"] != "directory", x["name"]))
    
    async def create_zip(
        self,
        archive_path: str,
        sources: list[str],
        user_id: int,
    ) -> Path:
        """
        Создание ZIP архива.
        
        Args:
            archive_path: Путь к создаваемому архиву
            sources: Список путей для архивации
            user_id: ID пользователя
            
        Returns:
            Путь к созданному архиву
        """
        try:
            archive_full_path = resolve_secure_path(archive_path)
            source_paths = [resolve_secure_path(s) for s in sources]
            
            result_path = safe_create_zip(source_paths, archive_full_path)
            
            # Сохранение в БД
            async with db.session() as session:
                file_record = File(
                    filename=result_path.name,
                    size=result_path.stat().st_size,
                    location=archive_path,
                    owner_id=user_id
                )
                session.add(file_record)
                await session.flush()
                
                operation = Operation(
                    operation_type=OperationType.CREATE,
                    file_id=file_record.id,
                    user_id=user_id
                )
                session.add(operation)
                await session.commit()
            
            return result_path
        except ArchiveSecurityError as e:
            raise ValueError(f"Ошибка безопасности при создании архива: {e}")
    
    async def extract_zip(
        self,
        archive_path: str,
        destination: str,
    ) -> list[Path]:
        """
        Распаковка ZIP архива.
        
        Args:
            archive_path: Путь к архиву
            destination: Путь назначения
            
        Returns:
            Список распакованных файлов
        """
        try:
            archive_full_path = resolve_secure_path(archive_path)
            dest_full_path = resolve_secure_path(destination)
            
            if not archive_full_path.exists():
                raise FileNotFoundError(f"Архив '{archive_path}' не найден")
            
            return safe_extract_zip(archive_full_path, dest_full_path)
        except ArchiveSecurityError as e:
            raise ValueError(f"Ошибка безопасности при распаковке архива: {e}")


# Глобальный экземпляр менеджера файлов
file_manager = FileManager()

