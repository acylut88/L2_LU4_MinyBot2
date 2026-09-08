import asyncio
import sys
import os

# Корректный импорт модулей из структуры проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from setup_wizard import BotSetupWizard
from vision.bot_manager import BotManager

async def main():
    # 1. Запускаем интерактивный мастер настройки параметров
    wizard = BotSetupWizard()
    profile_name, combat_name = wizard.run_interactive_menu()
    
    # 2. Передаем собранные параметры в главный оркестратор
    manager = BotManager(profile_name=profile_name, combat_profile_name=combat_name)
    
    try:
        await manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
