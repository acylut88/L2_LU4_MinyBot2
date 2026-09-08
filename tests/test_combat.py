import asyncio
import sys
import os
import keyboard  # Импортируем библиотеку для глобальных горячих клавиш

# Добавляем корень проекта в пути импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.state_tracker import StateTracker
from vision.target_validator import TargetValidator
from combat_profiles.summoner import SummonerCombat
from arduino.arduino_controller_async import AsyncArduinoController

class BotManager:
    def __init__(self, profile_name="PK_den4ika"):
        self.profile_name = profile_name
        
        # Инициализация всех подсистем проекта в одном месте
        self.arduino = AsyncArduinoController()
        self.tracker = StateTracker(profile_name=self.profile_name)
        self.validator = TargetValidator(profile_name=self.profile_name)
        self.bot_combat = SummonerCombat(self.tracker, self.validator, self.arduino)
        
        # Задачи asyncio для управления потоками
        self.tracker_task = None
        self.combat_task = None
        self.loop = None

    async def initialize_all(self) -> bool:
        """Пошаговый запуск и калибровка всех подсистем."""
        print("=== ИНИЦИАЛИЗАЦИЯ СИСТЕМ УПРАВЛЕНИЯ БОТОМ ===")
        
        # 1. Подключение к Arduino
        if not await self.arduino.connect():
            print("[Ошибка] Нет связи с Arduino Leonardo. Выход.")
            return False

        # 2. Настройка зрения ХП
        if not self.tracker.load_profile():
            print("[Калибровка] Профиль ХП не найден. Запуск калибровки полосы...")
            self.tracker.calibrate()

        # 3. Настройка валидатора Босса
        if not self.validator.load_profile():
            print("[Калибровка] Профиль зоны босса не найден. Запуск калибровки рамки...")
            self.validator.calibrate_target_zone()

        return True

    def toggle_pause(self):
        """Метод переключения состояния паузы (вызывается из хука клавиатуры)."""
        # Переключаем флаг паузы в боевом классе
        self.bot_combat.is_paused = not self.bot_combat.is_paused
        
        if self.bot_combat.is_paused:
            print("\n" + "="*40)
            print("[ПАУЗА] Бот временно остановлен клавишей 'P'.")
            print("="*40 + "\n")
        else:
            print("\n" + "="*40)
            print("[РАБОТА] Бот возобновил фарм клавишей 'P'.")
            print("="*40 + "\n")

    def setup_hotkeys(self):
        """Регистрация глобального хука на клавишу 'P'."""
        self.loop = asyncio.get_running_loop()
        
        # keyboard работает в отдельном потоке ОС Windows.
        # Чтобы безопасно изменить состояние флага в asyncio, используем call_soon_threadsafe
        keyboard.add_hotkey('p', lambda: self.loop.call_soon_threadsafe(self.toggle_pause))
        print("[Система] Глобальная горячая клавиша 'P' (Пауза/Старт) успешно зарегистрирована.")

    async def run(self):
        """Запуск параллельного выполнения задач."""
        if not await self.initialize_all():
            return

        # Настраиваем перехват клавиш
        self.setup_hotkeys()
        
        print("\n[Успешно] Все системы запущены. Начнем охоту через 2 секунды!")
        print("-> Нажмите английскую букву 'P' в любой момент для паузы или продолжения.\n")
        await asyncio.sleep(2)
        
        # Создаем параллельные асинхронные задачи
        self.tracker_task = asyncio.create_task(self.tracker.track_loop())
        self.combat_task = asyncio.create_task(self.bot_combat.start_loop())
        
        # Удерживаем задачи активными
        await asyncio.gather(self.tracker_task, self.combat_task)

    def shutdown(self):
        """Корректное закрытие всех соединений при выходе."""
        print("\n[Выход] Остановка всех подсистем менеджера...")
        if self.tracker_task: self.tracker_task.cancel()
        if self.combat_task: self.combat_task.cancel()
        keyboard.remove_all_hotkeys()
        self.arduino.close()
        print("[Готово] Бот полностью отключен.")

async def main():
    # Создаем единый менеджер управления
    manager = BotManager(profile_name="PK_den4ika")
    try:
        await manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
