"""Модуль для получения информации о дисках"""
import shutil
import platform
from typing import List, Dict


def get_disk_info() -> List[Dict]:
    """
    Получить информацию о дисках системы.
    
    Returns:
        Список словарей с информацией о дисках
    """
    disks = []
    
    try:
        import psutil
        
        partitions = psutil.disk_partitions()
        for partition in partitions:
            try:
                usage = shutil.disk_usage(partition.mountpoint)
                disks.append({
                    "name": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "usage_percent": (usage.used / usage.total * 100) if usage.total > 0 else 0,
                })
            except (PermissionError, OSError):
                continue
    except ImportError:
        # Fallback на shutil для базовой информации
        if platform.system() == "Windows":
            import string
            for drive_letter in string.ascii_uppercase:
                drive = f"{drive_letter}:\\"
                try:
                    usage = shutil.disk_usage(drive)
                    disks.append({
                        "name": drive,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "usage_percent": (usage.used / usage.total * 100) if usage.total > 0 else 0,
                    })
                except (OSError, PermissionError):
                    continue
        else:
            # Linux/Unix fallback
            try:
                usage = shutil.disk_usage("/")
                disks.append({
                    "name": "/",
                    "mountpoint": "/",
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "usage_percent": (usage.used / usage.total * 100) if usage.total > 0 else 0,
                })
            except (OSError, PermissionError):
                pass
    
    return disks


def format_bytes(bytes_count: int) -> str:
    """Форматирование размера в байтах"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"

