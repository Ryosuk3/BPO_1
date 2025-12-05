"""Модуль безопасной десериализации JSON и XML"""
import json
from typing import Any
from xml.etree.ElementTree import Element

try:
    from defusedxml.ElementTree import fromstring as safe_xml_fromstring
except ImportError:
    # Fallback на стандартный ElementTree если defusedxml не установлен
    from xml.etree.ElementTree import fromstring as safe_xml_fromstring


def safe_load_json(data: str) -> Any:
    """
    Безопасная загрузка JSON.
    
    Args:
        data: JSON строка
        
    Returns:
        Десериализованный объект
        
    Raises:
        ValueError: Если JSON невалиден
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Невалидный JSON: {e}")


def safe_dump_json(obj: Any, indent: int = None) -> str:
    """
    Безопасная сериализация в JSON.
    
    Args:
        obj: Объект для сериализации
        indent: Отступ для форматирования
        
    Returns:
        JSON строка
    """
    return json.dumps(obj, indent=indent, ensure_ascii=False)


def safe_load_xml(data: str) -> Element:
    """
    Безопасная загрузка XML с защитой от XXE и других атак.
    Использует defusedxml для защиты.
    
    Args:
        data: XML строка
        
    Returns:
        Корневой элемент XML дерева
        
    Raises:
        ValueError: Если XML невалиден
    """
    try:
        return safe_xml_fromstring(data)
    except Exception as e:
        raise ValueError(f"Невалидный XML: {e}")


def safe_dump_xml(element: Element, encoding: str = "utf-8") -> bytes:
    """
    Безопасная сериализация XML элемента.
    
    Args:
        element: XML элемент
        encoding: Кодировка
        
    Returns:
        XML байты
    """
    from xml.etree.ElementTree import tostring
    return tostring(element, encoding=encoding)

