import asyncio
import sys
import os
import json
import keyboard
import win32gui
import win32con

try:
    from ctypes import windll
    windll.user32.SetProcessDPIAware()
except Exception as e:
    print("DPI Awareness предупреждение:", e)

from vision.hp_tracker import HPTracker
from vision.target_validator import TargetValidator
from vision.summoner_combat import SummonerCombat
from vision.buff_system import BuffSystem  # Импортируем нашу систему баффов
from arduino.arduino_controller_async import AsyncArduinoController

class BotManager:
    def __init__(self, profile_name="PK_den4ika"):
        self.profile_name = profile_name
        
        vision_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(vision_dir), "config.json")
        
        self.main_nick, self.second_nick = self._load_window_nicks()
        self.hwnd_main = None
        self.hwnd_second = None
        
        # Инициализация ядра
        self.arduino = AsyncArduinoController()
        
        # Зрение и бой моба
        self.tracker = HPTracker(profile_name=self.profile_name)
        self.validator = TargetValidator(profile_name=self.profile_name)
        
        # Системы поддержки и кача
        self.buff_system = BuffSystem(self.arduino)
        
        # Передаем только то, что реально работает: трекер, валидатор, ардуино и баффы
        self.bot_combat = SummonerCombat(self.tracker, self.validator, self.arduino, self.buff_system)
        
        self.tracker_task = None
        self.combat_task = None

    def _load_window_nicks(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            w_settings = config.get("game_windows", {})
            return w_settings.get("Main_Window", "UnReviver"), w_settings.get("Second_Window", "Acylut")
        except Exception:
            return "UnReviver", "Acylut"

    def _find_game_windows(self) -> bool:
        title_main = f"LU4 - {self.main_nick}"
        title_second = f"LU4 - {self.second_nick}"
        
        self.hwnd_main = win32gui.FindWindow(None, title_main)
        self.hwnd_second = win32gui.FindWindow(None, title_second)
        
        if not self.hwnd_main:
            print(f"[Окна] Предупреждение: Основное окно '{title_main}' не найдено.")
        else:
            print(f"[Окна] Привязано основное окно (HWND: {self.hwnd_main})")
            
        if not self.hwnd_second:
            print(f"[Окна] Предупреждение: Второе окно '{title_second}' не найдено.")
        else:
            print(f"[Окна] Привязано второе окно (HWND: {self.hwnd_second})")
            
        return bool(self.hwnd_main or self.hwnd_second)

    async def activate_window(self, target="main"):
        hwnd = self.hwnd_main if target == "main" else self.hwnd_second
        nick = self.main_nick if target == "main" else self.second_nick
        
        if not hwnd or not win32gui.IsWindow(hwnd):
            print(f"[Окна] Ошибка: Окно {nick} недоступно.")
            return False
            
        if win32gui.GetForegroundWindow() == hwnd:
            return True
            
        print(f"[Окна] Активация окна персонажа: {nick}...")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        
        await asyncio.sleep(0.2)
        return True

    async def initialize_all(self) -> bool:
        print("=== ИНИЦИАЛИЗАЦИЯ СИСТЕМ УПРАВЛЕНИЯ БОТОМ ===")
        
        self._find_game_windows()
        
        if not await self.arduino.connect():
            print("[Ошибка] Нет связи с Arduino. Выход.")
            return False

        await self.activate_window("main")

        if not self.tracker.load_profile():
            print("[Калибровка] Настройка ХП моба...")
            self.tracker.calibrate()

        if not self.validator.load_profile():
            print("[Калибровка] Настройка рамки босса...")
            self.validator.calibrate_target_zone()

        return True

    def toggle_pause(self):
        """Переключатель глобальной паузы для всех подсистем."""
        self.bot_combat.is_paused = not self.bot_combat.is_paused
        self.tracker.is_paused = self.bot_combat.is_paused
        
        # Передаем состояние паузы в систему баффов
        self.buff_system.is_paused = self.bot_combat.is_paused
        
        if self.bot_combat.is_paused:
            print(f"\n{'='*40}\n[ПАУЗА] Бот остановлен клавишей 'P'. Логи и баффы заморожены.\n{'='*40}\n")
        else:
            print(f"\n{'='*40}\n[РАБОТА] Бот возобновил фарм клавишей 'P'.\n{'='*40}\n")

    def setup_hotkeys(self):
        self.loop = asyncio.get_running_loop()
        keyboard.add_hotkey('p', lambda: self.loop.call_soon_threadsafe(self.toggle_pause))
        print("[Система] Глобальная горячая клавиша 'P' (Пауза/Старт) зарегистрирована.")

    async def run(self):
        if not await self.initialize_all():
            return

        self.setup_hotkeys()
        
        print("\n[Успешно] Все подсистемы запущены.")
        print("-> Автоматическое переключение на окно сумонера через 2 сек...\n")
        await asyncio.sleep(2)
        
        await self.activate_window("main")
        
        # 1. Запускаем стартовый фулл-бафф (прожмет Num1-Num9)
        await self.buff_system.buff_all_at_start()
        
        # 2. Включаем циклические независимые таймеры ребаффа
        self.buff_system.start_buff_timers()
        
        # 3. Запускаем параллельные задачи кача и зрения
        self.tracker_task = asyncio.create_task(self.tracker.track_loop())
        self.combat_task = asyncio.create_task(self.bot_combat.start_loop())
        
        await asyncio.gather(self.tracker_task, self.combat_task)

    def shutdown(self):
        print("\n[Выход] Закрытие ресурсов менеджера...")
        if self.tracker_task: self.tracker_task.cancel()
        if self.combat_task: self.combat_task.cancel()
        
        # Выключаем таймеры баффов при выходе
        self.buff_system.stop_buff_timers()
        
        keyboard.remove_all_hotkeys()
        self.arduino.close()
        print("[Готово] Бот полностью отключен.")
