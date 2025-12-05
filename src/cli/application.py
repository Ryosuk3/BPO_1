
import asyncio
import shlex
from pathlib import Path
from typing import Optional

from src.core.config import config
from src.core.database import db
from src.core.models import Base
from src.core.security import resolve_secure_path
from src.users.auth import create_user, authenticate_user
from src.files.manager import file_manager
from src.system.disks import get_disk_info, format_bytes


class ApplicationState:
    """Состояние приложения"""
    def __init__(self):
        self.current_user_id: Optional[int] = None
        self.current_path: str = "."
    
    def get_current_relative_path(self) -> str:
        """Получить текущий относительный путь"""
        return self.current_path if self.current_path != "." else ""


class CLIApplication:
    """Интерактивное CLI приложение"""
    
    def __init__(self):
        self.state = ApplicationState()
        self.running = True
    
    async def initialize(self):
        """Инициализация приложения"""
        await db.connect()
        
        # Создание таблиц
        if db._engine:
            async with db._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        
        print("Безопасный файловый менеджер")
        print("Введите 'help' для списка команд или 'exit' для выхода")
        print()
    
    async def cleanup(self):
        """Очистка ресурсов"""
        await db.disconnect()
    
    def print_prompt(self):
        """Вывод приглашения к вводу"""
        path = self.state.get_current_relative_path()
        if path:
            print(f"{path}> ", end="", flush=True)
        else:
            print("/> ", end="", flush=True)
    
    async def handle_command(self, command_line: str):
        """Обработка команды"""
        if not command_line.strip():
            return
        
        parts = shlex.split(command_line)
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        try:
            if cmd == "exit":
                self.running = False
            elif cmd == "help":
                self.print_help()
            elif cmd == "register":
                await self.cmd_register()
            elif cmd == "login":
                await self.cmd_login()
            elif cmd == "logout":
                await self.cmd_logout()
            elif cmd == "pwd":
                await self.cmd_pwd()
            elif cmd == "ls":
                await self.cmd_ls(args)
            elif cmd == "cd":
                await self.cmd_cd(args)
            elif cmd == "clear":
                self.cmd_clear()
            elif cmd == "disk":
                await self.cmd_disk()
            elif cmd == "touch":
                await self.cmd_touch(args)
            elif cmd == "rm":
                await self.cmd_rm(args)
            elif cmd == "cat":
                await self.cmd_cat(args)
            elif cmd == "wr":
                await self.cmd_wr(args)
            elif cmd == "mkdir":
                await self.cmd_mkdir(args)
            elif cmd == "rmdir":
                await self.cmd_rmdir(args)
            elif cmd == "mv":
                await self.cmd_mv(args)
            elif cmd == "zip":
                await self.cmd_zip(args)
            elif cmd == "unzip":
                await self.cmd_unzip(args)
            else:
                print(f"Неизвестная команда: {cmd}. Введите 'help' для списка команд.")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def print_help(self):
        """Вывод справки"""
        help_text = """
Доступные команды:

Пользователи:
  register              - Регистрация нового пользователя
  login                 - Вход в систему
  logout                - Выход из системы

Навигация:
  pwd                   - Показать текущий путь
  ls [path]             - Список файлов и директорий
  cd <path>             - Перейти в директорию (используйте '..' для подъема)
  clear                 - Очистить экран

Диски:
  disk                  - Информация о дисках системы

Файлы:
  touch <name>          - Создать файл
  rm <name>             - Удалить файл
  cat <name>            - Показать содержимое файла
  wr <name> <content>   - Записать/добавить содержимое в файл

Директории:
  mkdir <name>          - Создать директорию
  rmdir <name> [-r]     - Удалить директорию (используйте -r для рекурсивного удаления)

Операции:
  mv <source> <dest>    - Переместить файл или директорию
  zip <archive> <src...> - Создать ZIP архив
  unzip <archive> <dest> - Распаковать ZIP архив

Прочее:
  help                  - Показать эту справку
  exit                  - Выход из программы
"""
        print(help_text)
    
    async def cmd_register(self):
        """Регистрация пользователя"""
        username = input("Введите логин: ").strip()
        if not username:
            print("Логин не может быть пустым")
            return
        
        password = self.get_password("Введите пароль: ")
        password2 = self.get_password("Повторите пароль: ")
        
        if password != password2:
            print("Пароли не совпадают")
            return
        
        try:
            user = await create_user(username, password)
            print(f"Пользователь '{username}' успешно зарегистрирован")
        except ValueError as e:
            print(f"Ошибка регистрации: {e}")
    
    async def cmd_login(self):
        """Вход в систему"""
        username = input("Введите логин: ").strip()
        password = self.get_password("Введите пароль: ")
        
        user = await authenticate_user(username, password)
        if user:
            self.state.current_user_id = user.id
            print(f"Добро пожаловать, {username}!")
        else:
            print("Неверный логин или пароль")
    
    async def cmd_logout(self):
        """Выход из системы"""
        self.state.current_user_id = None
        print("Вы вышли из системы")
    
    def get_password(self, prompt: str) -> str:
        """Безопасный ввод пароля"""
        import getpass
        return getpass.getpass(prompt)
    
    async def cmd_pwd(self):
        """Показать текущий путь"""
        path = self.state.get_current_relative_path()
        print(path if path else "/")
    
    async def cmd_ls(self, args: list):
        """Список файлов и директорий"""
        path = args[0] if args else self.state.get_current_relative_path()
        if not path:
            path = "."
        
        try:
            items = await file_manager.list_directory(path)
            for item in items:
                if item["type"] == "directory":
                    print(f"[DIR]  {item['name']}")
                else:
                    size_str = format_bytes(item["size"])
                    print(f"       {item['name']:<30} {size_str:>10}")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_cd(self, args: list):
        """Переход в директорию"""
        if not args:
            print("Использование: cd <path>")
            return
        
        path = args[0]
        
        if path == "..":
            # Подъем на уровень вверх
            current = self.state.get_current_relative_path()
            if current:
                parent = str(Path(current).parent)
                self.state.current_path = parent if parent != "." else "."
            else:
                self.state.current_path = "."
        else:
            # Объединяем текущий путь с новым
            current = self.state.get_current_relative_path()
            if current:
                new_path = str(Path(current) / path)
            else:
                new_path = path
            
            # Проверяем существование
            try:
                full_path = resolve_secure_path(new_path)
                if full_path.exists() and full_path.is_dir():
                    self.state.current_path = new_path
                else:
                    print(f"Директория '{new_path}' не найдена")
            except Exception as e:
                print(f"Ошибка: {e}")
    
    def cmd_clear(self):
        """Очистка экрана"""
        import os
        os.system("cls" if os.name == "nt" else "clear")
    
    async def cmd_disk(self):
        """Информация о дисках"""
        try:
            disks = get_disk_info()
            for disk in disks:
                print(f"\nДиск: {disk.get('name', disk.get('mountpoint', 'N/A'))}")
                print(f"  Всего: {format_bytes(disk['total'])}")
                print(f"  Использовано: {format_bytes(disk['used'])} ({disk['usage_percent']:.1f}%)")
                print(f"  Свободно: {format_bytes(disk['free'])}")
        except Exception as e:
            print(f"Ошибка получения информации о дисках: {e}")
            print("Примечание: Для Windows требуется pywin32, для Linux - psutil")
    
    async def cmd_touch(self, args: list):
        """Создание файла"""
        if not args:
            print("Использование: touch <name>")
            return
        
        if not self.state.current_user_id:
            print("Необходимо войти в систему")
            return
        
        name = args[0]
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            await file_manager.create_file(full_name, self.state.current_user_id)
            print(f"Файл '{name}' создан")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_rm(self, args: list):
        """Удаление файла"""
        if not args:
            print("Использование: rm <name>")
            return
        
        if not self.state.current_user_id:
            print("Необходимо войти в систему")
            return
        
        name = args[0]
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            await file_manager.delete_file(full_name, self.state.current_user_id)
            print(f"Файл '{name}' удален")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_cat(self, args: list):
        """Показать содержимое файла"""
        if not args:
            print("Использование: cat <name>")
            return
        
        name = args[0]
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            content = await file_manager.read_file(full_name)
            print(content)
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_wr(self, args: list):
        """Запись в файл"""
        if len(args) < 2:
            print("Использование: wr <name> <content>")
            return
        
        if not self.state.current_user_id:
            print("Необходимо войти в систему")
            return
        
        name = args[0]
        content = " ".join(args[1:])
        
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            await file_manager.write_file(full_name, content, self.state.current_user_id, append=True)
            print(f"Содержимое записано в '{name}'")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_mkdir(self, args: list):
        """Создание директории"""
        if not args:
            print("Использование: mkdir <name>")
            return
        
        name = args[0]
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            await file_manager.create_directory(full_name)
            print(f"Директория '{name}' создана")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_rmdir(self, args: list):
        """Удаление директории"""
        if not args:
            print("Использование: rmdir <name> [-r]")
            return
        
        recursive = "-r" in args or "--recursive" in args
        name = args[0] if args[0] not in ["-r", "--recursive"] else args[1] if len(args) > 1 else None
        
        if not name:
            print("Использование: rmdir <name> [-r]")
            return
        
        current = self.state.get_current_relative_path()
        if current:
            full_name = str(Path(current) / name)
        else:
            full_name = name
        
        try:
            await file_manager.delete_directory(full_name, recursive=recursive)
            print(f"Директория '{name}' удалена")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_mv(self, args: list):
        """Перемещение файла или директории"""
        if len(args) < 2:
            print("Использование: mv <source> <destination>")
            return
        
        source = args[0]
        dest = args[1]
        
        current = self.state.get_current_relative_path()
        if current:
            source_full = str(Path(current) / source)
            dest_full = str(Path(current) / dest)
        else:
            source_full = source
            dest_full = dest
        
        try:
            await file_manager.move(source_full, dest_full)
            print(f"'{source}' перемещен в '{dest}'")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_zip(self, args: list):
        """Создание ZIP архива"""
        if len(args) < 2:
            print("Использование: zip <archive> <src...>")
            return
        
        if not self.state.current_user_id:
            print("Необходимо войти в систему")
            return
        
        archive = args[0]
        sources = args[1:]
        
        current = self.state.get_current_relative_path()
        if current:
            archive_full = str(Path(current) / archive)
            sources_full = [str(Path(current) / s) for s in sources]
        else:
            archive_full = archive
            sources_full = sources
        
        try:
            await file_manager.create_zip(archive_full, sources_full, self.state.current_user_id)
            print(f"Архив '{archive}' создан")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def cmd_unzip(self, args: list):
        """Распаковка ZIP архива"""
        if len(args) < 2:
            print("Использование: unzip <archive> <destination>")
            return
        
        archive = args[0]
        destination = args[1]
        
        current = self.state.get_current_relative_path()
        if current:
            archive_full = str(Path(current) / archive)
            dest_full = str(Path(current) / destination)
        else:
            archive_full = archive
            dest_full = destination
        
        try:
            files = await file_manager.extract_zip(archive_full, dest_full)
            print(f"Архив '{archive}' распакован в '{destination}' ({len(files)} файлов)")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    async def run(self):
        """Запуск приложения"""
        await self.initialize()
        
        try:
            while self.running:
                try:
                    self.print_prompt()
                    command_line = input().strip()
                    if command_line:
                        await self.handle_command(command_line)
                except EOFError:
                    print("\nВыход...")
                    break
                except KeyboardInterrupt:
                    print("\nВыход...")
                    break
        finally:
            await self.cleanup()

