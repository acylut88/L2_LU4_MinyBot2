# version2/auto_calibrator/bot_initializer.py
import asyncio

class BotInitializer:
    def __init__(self, core):
        self.core = core

    async def run_system(self):
        """Полный запуск всех аппаратных и пиксельных шин бота."""
        print("=" * 60)
        print("   ЗАПУСК АППАРАТНОГО ДВИЖКА (ПОЛНЫЙ ФАРМ С ARDUINO)   ")
        print("=" * 60)
        
        # 1. Коннект к плате Leonardo
        if not await self.core.arduino.connect():
            print("[Критическая Ошибка] Робот заблокирован: нет связи!")
            return
            
        # 2. Подгружаем OpenCV профиль черепа босса
        self.core.validator.load_profile()
        
        # 3. Передаем логгер в модуль защиты
        self.core.defense.logger = self.core.logger
        
        # 4. Собираем и запускаем параллельные задачи
        await asyncio.gather(
            self.core.bus.start_loop(),
            self.core.defense.start_loop(),
            self.core.combat_main_loop()
        )
