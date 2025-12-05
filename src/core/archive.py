"""Модуль безопасной работы с ZIP архивами (защита от ZIP-бомб)"""
import zipfile
from pathlib import Path
from typing import List
from src.core.config import config
from src.core.security import resolve_secure_path, validate_filename


class ArchiveSecurityError(Exception):
    """Ошибка безопасности при работе с архивом"""
    pass


def validate_zip_entry(entry: zipfile.ZipInfo) -> None:
    """
    Валидация записи в ZIP архиве на предмет ZIP-бомбы.
    
    Args:
        entry: Информация о записи в архиве
        
    Raises:
        ArchiveSecurityError: Если обнаружена подозрительная запись
    """
    # Проверка коэффициента сжатия
    if entry.compress_size > 0:
        ratio = entry.file_size / entry.compress_size
        if ratio > config.ZIP_MAX_RATIO:
            raise ArchiveSecurityError(
                f"Подозрительно высокий коэффициент сжатия ({ratio:.2f}) "
                f"для файла '{entry.filename}'. Возможна ZIP-бомба."
            )
    elif entry.file_size > 0:
        # Сжатый размер 0, но распакованный > 0 - подозрительно
        raise ArchiveSecurityError(
            f"Файл '{entry.filename}' имеет нулевой сжатый размер, "
            f"но ненулевой размер после распаковки."
        )


def validate_zip_file(zip_path: Path) -> dict:
    """
    Валидация ZIP файла перед распаковкой.
    
    Args:
        zip_path: Путь к ZIP файлу
        
    Returns:
        Словарь с информацией о валидации
        
    Raises:
        ArchiveSecurityError: Если архив небезопасен
    """
    total_uncompressed = 0
    total_compressed = 0
    file_count = 0
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for entry in zf.infolist():
                file_count += 1
                
                if file_count > config.ZIP_MAX_FILES:
                    raise ArchiveSecurityError(
                        f"Превышено максимальное количество файлов в архиве "
                        f"({config.ZIP_MAX_FILES})"
                    )
                
                # Валидация записи
                validate_zip_entry(entry)
                
                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size or 0
                
                if total_uncompressed > config.ZIP_MAX_TOTAL_SIZE:
                    raise ArchiveSecurityError(
                        f"Общий размер распакованных данных превышает лимит "
                        f"({config.ZIP_MAX_TOTAL_SIZE} байт)"
                    )
    except zipfile.BadZipFile:
        raise ArchiveSecurityError("Файл не является валидным ZIP архивом")
    
    return {
        "file_count": file_count,
        "total_uncompressed": total_uncompressed,
        "total_compressed": total_compressed,
    }


def safe_extract_zip(
    zip_path: Path,
    destination: Path,
    max_depth: int = None,
) -> List[Path]:
    """
    Безопасная распаковка ZIP архива с защитой от ZIP-бомб и Zip Slip.
    
    Args:
        zip_path: Путь к ZIP архиву
        destination: Путь назначения
        max_depth: Максимальная глубина вложенности (по умолчанию из config)
        
    Returns:
        Список распакованных файлов
        
    Raises:
        ArchiveSecurityError: Если обнаружена угроза безопасности
    """
    if max_depth is None:
        max_depth = config.ZIP_MAX_RECURSION_DEPTH
    
    if max_depth <= 0:
        raise ArchiveSecurityError("Превышена максимальная глубина вложенности архивов")
    
    # Валидация архива перед распаковкой
    validate_zip_file(zip_path)
    
    # Безопасное разрешение пути назначения
    dest_path = resolve_secure_path(str(destination))
    dest_path.mkdir(parents=True, exist_ok=True)
    
    extracted_files = []
    dest_resolved = dest_path.resolve()
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for entry in zf.namelist():
                # Защита от Zip Slip (Path Traversal в архивах)
                # Нормализуем путь и проверяем, что он внутри destination
                entry_path = Path(entry)
                if entry_path.is_absolute() or ".." in entry_path.parts:
                    raise ArchiveSecurityError(
                        f"Обнаружена попытка Zip Slip: '{entry}'"
                    )
                
                full_entry_path = (dest_path / entry_path).resolve()
                
                # Критическая проверка: путь должен быть внутри destination
                if not str(full_entry_path).startswith(str(dest_resolved)):
                    raise ArchiveSecurityError(
                        f"Обнаружена попытка выхода за пределы назначения: '{entry}'"
                    )
                
                # Получаем информацию о записи
                entry_info = zf.getinfo(entry)
                
                # Дополнительная валидация
                validate_zip_entry(entry_info)
                
                # Создаем директории если нужно
                if entry.endswith('/'):
                    full_entry_path.mkdir(parents=True, exist_ok=True)
                else:
                    # Создаем родительские директории
                    full_entry_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Распаковываем файл с проверкой размера
                    with zf.open(entry) as source:
                        with open(full_entry_path, 'wb') as target:
                            # Читаем порциями для контроля размера
                            total_size = 0
                            chunk_size = 8192
                            
                            while True:
                                chunk = source.read(chunk_size)
                                if not chunk:
                                    break
                                
                                total_size += len(chunk)
                                if total_size > config.ZIP_MAX_TOTAL_SIZE:
                                    raise ArchiveSecurityError(
                                        "Превышен максимальный размер распаковки"
                                    )
                                
                                target.write(chunk)
                    
                    extracted_files.append(full_entry_path)
                    
                    # Проверка на вложенные архивы
                    if entry.lower().endswith('.zip'):
                        # Рекурсивная распаковка с уменьшенной глубиной
                        extracted_files.extend(
                            safe_extract_zip(
                                full_entry_path,
                                full_entry_path.parent / full_entry_path.stem,
                                max_depth - 1
                            )
                        )
    
    except zipfile.BadZipFile:
        raise ArchiveSecurityError("Файл не является валидным ZIP архивом")
    
    return extracted_files


def safe_create_zip(
    sources: List[Path],
    destination: Path,
) -> Path:
    """
    Безопасное создание ZIP архива.
    
    Args:
        sources: Список путей для архивации
        destination: Путь к создаваемому архиву
        
    Returns:
        Путь к созданному архиву
        
    Raises:
        ArchiveSecurityError: Если обнаружена проблема безопасности
    """
    # Валидация пути назначения
    dest_path = resolve_secure_path(str(destination))
    validate_filename(dest_path.name)
    
    # Проверка источников
    total_size = 0
    file_count = 0
    
    for source in sources:
        source_path = resolve_secure_path(str(source))
        
        if source_path.is_file():
            file_count += 1
            total_size += source_path.stat().st_size
        elif source_path.is_dir():
            # Рекурсивный подсчет файлов в директории
            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size
                    
                    if file_count > config.ZIP_MAX_FILES:
                        raise ArchiveSecurityError(
                            f"Превышено максимальное количество файлов ({config.ZIP_MAX_FILES})"
                        )
                    
                    if total_size > config.ZIP_MAX_TOTAL_SIZE:
                        raise ArchiveSecurityError(
                            f"Превышен максимальный размер для архивации ({config.ZIP_MAX_TOTAL_SIZE} байт)"
                        )
        else:
            raise ArchiveSecurityError(f"Источник не найден: {source}")
    
    # Создание архива
    try:
        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for source in sources:
                source_path = resolve_secure_path(str(source))
                
                if source_path.is_file():
                    zf.write(source_path, source_path.name)
                elif source_path.is_dir():
                    for file_path in source_path.rglob('*'):
                        if file_path.is_file():
                            # Относительный путь внутри архива
                            arcname = file_path.relative_to(source_path.parent)
                            zf.write(file_path, arcname)
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise ArchiveSecurityError(f"Ошибка при создании архива: {e}")
    
    return dest_path

