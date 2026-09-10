# version2/main.py
import asyncio
import sys
import os

# Фиксируем пути импорта, чтобы Python видел модули внутри version2
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from auto_calibrator.universal_core import UniversalBotCore

async def main():
    print("=" * 60)
    print("   ЗАПУСК ОБНОВЛЕННОГО АСИНХРОННОГО ДВИЖКА (ВЕРСИЯ 2)   ")
    print("=" * 60)
    
    # Запускаем движок. Он подтянет calibrator.json и config.json из папки version2
    bot = UniversalBotCore()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n[Главный поток] Работа бота успешно остановлена пользователем.")
    finally:
        # Безопасное закрытие COM-порта Ардуино при выходе
        if hasattr(bot, 'arduino') and bot.arduino:
            bot.arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
