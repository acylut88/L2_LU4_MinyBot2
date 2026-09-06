import asyncio
import sys
import os

# Корректный импорт модулей из структуры проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision.bot_manager import BotManager

async def main():
    # Создаем единый менеджер управления под нужный профиль
    manager = BotManager(profile_name="PK_den4ika")
    try:
        await manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
