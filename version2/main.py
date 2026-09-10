# version2/main.py
import asyncio
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from auto_calibrator.universal_core import UniversalBotCore

async def main():
    print("=" * 60)
    print("   ЗАПУСК АППАРАТНОГО ДВИЖКА (ПОЛНЫЙ ФАРМ С ARDUINO v2)   ")
    print("=" * 60)
    
    bot = UniversalBotCore()
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n[Главный поток] Фарм успешно остановлен пользователем.")
    finally:
        if hasattr(bot, 'arduino') and bot.arduino:
            bot.arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
