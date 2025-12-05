"""Главный файл приложения"""
import asyncio
from src.cli.application import CLIApplication


async def main():
    """Точка входа в приложение"""
    app = CLIApplication()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())

