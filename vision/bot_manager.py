import asyncio
import sys
import os
import json
import keyboard
import win32gui
import win32con
import importlib
from vision.state_tracker import StateTracker
from vision.target_validator import TargetValidator
from vision.buff_system import BuffSystem  
from arduino.arduino_controller_async import AsyncArduinoController 
from vision.frame_bus import FrameBus



try:
    from ctypes import windll
    windll.user32.SetProcessDPIAware()
except Exception as e:
    print("DPI Awareness предупреждение:", e)


class BotManager:
    def __init__(self, profile_name="PK_den4ika", combat_profile_name="summoner"):
        self.profile_name = profile_name
        self.combat_profile_name = combat_profile_name
        
        vision_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(vision_dir), "config.json")
        
        self.main_nick, self.second_nick = self._load_window_nicks()
        self.hwnd_main = None
        self.hwnd_second = None
        
        self.arduino = AsyncArduinoController()
        
        # 1. Инициализируем нашу новую единую шину кадров
        self.frame_bus = FrameBus(check_interval=0.05)
        
        # 2. Создаем трекеры шкал
        self.tracker = StateTracker(profile_name=self.profile_name, mode="target_hp")
        self.player_hp_tracker = StateTracker(profile_name=self.profile_name, mode="player_hp")
        self.player_mp_tracker = StateTracker(profile_name=self.profile_name, mode="player_mp")
        
        # 3. Регистрируем их в шине, чтобы они автоматом питались кадрами
        self.frame_bus.register_tracker(self.tracker)
        self.frame_bus.register_tracker(self.player_hp_tracker)
        self.frame_bus.register_tracker(self.player_mp_tracker)
        
        self.validator = TargetValidator(profile_name=self.profile_name)
        self.buff_system = BuffSystem(self.arduino)
        self.bot_combat = self._load_combat_profile()
        
        # Ссылки на асинхронные задачи
        self.tracker_task = None
        self.player_hp_task = None
        self.player_mp_task = None
        self.combat_task = None
        self.is_switching_context = False

    def _load_combat_profile(self):
        try:
            module_name = f"combat_profiles.{self.combat_profile_name}"
            module = importlib.import_module(module_name)
            class_name = f"{self.combat_profile_name.capitalize()}Combat"
            combat_class = getattr(module, class_name)
            print(f"[Движок] Успешно подгружен боевой класс '{class_name}' из '{module_name}.py'")
            return combat_class(self.tracker, self.validator, self.arduino, self.buff_system)
        except Exception as e:
            print(f"[Критическая ошибка] Не удалось загрузить профиль боя '{self.combat_profile_name}': {e}")
            from combat_profiles.summoner import SummonerCombat
            return SummonerCombat(self.tracker, self.validator, self.arduino, self.buff_system)

    def _load_window_nicks(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            w_settings = config.get("game_windows", {})
            self.bot_mode = w_settings.get("mode", "Single-Box")
            self.support_mode = w_settings.get("second_window_mode", 0)
            return w_settings.get("Main_Window", "UnReviver"), w_settings.get("Second_Window", "")
        except Exception:
            self.bot_mode = "Single-Box"
            self.support_mode = 0
            return "UnReviver", ""

    def _find_game_windows(self) -> bool:
        title_main = f"LU4 - {self.main_nick}"
        self.hwnd_main = win32gui.FindWindow(None, title_main)
        
        if not self.hwnd_main:
            print(f"[Окна] Предупреждение: Основное окно '{title_main}' не найдено.")
        else:
            print(f"[Окна] Привязано основное окно (HWND: {self.hwnd_main})")
            
        if getattr(self, 'bot_mode', 'Single-Box') == "Dual-Box" and self.second_nick:
            title_second = f"LU4 - {self.second_nick}"
            self.hwnd_second = win32gui.FindWindow(None, title_second)
            if not self.hwnd_second:
                print(f"[Окна] Предупреждение: Второе окно '{title_second}' не найдено.")
            else:
                print(f"[Окна] Привязано второе окно (HWND: {self.hwnd_second})")
        else:
            self.hwnd_second = None
            
        return bool(self.hwnd_main or (self.bot_mode == "Dual-Box" and self.hwnd_second))

    async def switch_window(self, target="main"):
        """Абсолютно устойчивый метод вывода окна игры на передний план с обходом ограничений ОС."""
        hwnd = self.hwnd_main if target == "main" else self.hwnd_second
        nick = self.main_nick if target == "main" else self.second_nick
        
        if not hwnd or not win32gui.IsWindow(hwnd):
            print(f"[Окна] Ошибка: Окно {nick} недоступно для активации.")
            return False
            
        if win32gui.GetForegroundWindow() == hwnd:
            return True
            
        try:
            print(f"[Окна] Попытка переключения фокуса на: {nick}...")
            
            # Шаг 1: Очищаем таргет на текущем активном окне перед уходом
            await self.arduino.send_button("Esc")
            await asyncio.sleep(0.05)
            
            # Шаг 2: Если окно свернуто на панель задач — восстанавливаем его геометрию
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                
            # Шаг 3: Сбрасываем блокировку фокуса Windows (симулируем нажатие системной клавиши ALT)
            # Это открывает права на SetForegroundWindow для фоновых скриптов
            import win32api
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0) # Нажали ALT
            win32gui.SetForegroundWindow(hwnd)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0) # Отпустили ALT
            
            # Даем видеокарте время отрисовать интерфейс окна
            await asyncio.sleep(0.3)
            return True
            
        except Exception as e:
            # Полная защита от вылета: если Windows всё же заблокировала фокус, 
            # перехватываем ошибку, чтобы корутины бота продолжали жить
            print(f"[Окна] Предупреждение: Активация {nick} выполнена в режиме фолбэка. Причина: {e}")
            await asyncio.sleep(0.5)
            return False

    async def request_recharge(self):
        """Процедура инвайта и заливки маны от Саппорта."""
        if self.bot_mode != "Dual-Box" or not self.hwnd_second:
            return False

        if self.support_mode not in self.buff_system.MODES_WITH_RECHARGE:
            return False
            
        if self.is_switching_context:
            return True
            
        self.is_switching_context = True
        print("\n" + "="*50)
        print("[Оркестратор] Мана дварфа низкая! Запуск пати-заливки...")
        print("="*50)
        
        self.bot_combat.is_paused = True
        
        print("[Мейн] Отправляем инвайт в группу саппорту (Кнопка 'F5')...")
        await self.arduino.send_button("F5")
        await asyncio.sleep(0.5)
        
        if await self.switch_window("second"):
            print("[Саппорт] Прожимаю макрос заливки маны (Кнопка '-')...")
            await self.arduino.send_button("-")
            await asyncio.sleep(3.2)
            await self.switch_window("main")
            
        self.bot_combat.is_paused = False
        self.is_switching_context = False
        print("[Оркестратор] Заливка завершена. Возврат к охоте.\n")
        return True

    async def initialize_all(self) -> bool:
        print("=== ИНИЦИАЛИЗАЦИЯ СИСТЕМ УПРАВЛЕНИЯ БОТОМ ===")
        self._find_game_windows()
        
        if not await self.arduino.connect():
            print("[Ошибка] Нет связи с Arduino. Выход.")
            return False

        await self.switch_window("main")

        if not self.tracker.load_profile():
            print("[Калибровка] Профиль разметки экрана не найден. Запустите мастер настройки!")
            return False

        if not self.validator.load_profile():
            print("[Калибровка] Профиль рамки босса не найден. Запуск разметки...")
            self.validator.calibrate_target_zone()

        return True

    def toggle_pause(self):
        # Меняем состояние паузы основного боевого цикла и систем
        self.bot_combat.is_paused = not self.bot_combat.is_paused
        self.tracker.is_paused = self.bot_combat.is_paused
        self.player_hp_tracker.is_paused = self.bot_combat.is_paused
        self.player_mp_tracker.is_paused = self.bot_combat.is_paused
        self.buff_system.is_paused = self.bot_combat.is_paused
        
        # Синхронизируем паузу самой шины захвата кадров
        self.frame_bus.is_paused = self.bot_combat.is_paused
        
        if self.bot_combat.is_paused:
            print(f"\n{'='*40}\n[ПАУЗА] Бот остановлен клавишей 'P'. Логи и кадры заморожены.\n{'='*40}\n")
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
        
        self.buff_system.bot_manager = self
        self.bot_combat.bot_manager = self
        
        print("\n[Успешно] Все подсистемы запущены.")
        print("-> Автоматическое переключение на окно персонажа через 2 сек...\n")
        await asyncio.sleep(2)
        
        await self.switch_window("main")
        self.buff_system.support_mode = self.support_mode
        await self.buff_system.buff_all_at_start()

        if self.bot_mode == "Dual-Box" and self.support_mode in self.buff_system.MODES_WITH_BUFF:
            print(f"[Движок] Запуск таймеров ребаффа для саппорта (Режим роли: {self.support_mode})")
            self.buff_system.start_buff_timers()
        else:
            print("[Движок] Фоновые таймеры баффа отключены для данной роли саппорта.")
        
        # 1. Запускаем центральную шину захвата кадров
        self.frame_bus.start()
        
        # 2. Запускаем параллельные асинхронные циклы анализа шкал
        self.tracker_task = asyncio.create_task(self.tracker.track_loop())
        self.player_hp_task = asyncio.create_task(self.player_hp_tracker.track_loop())
        self.player_mp_task = asyncio.create_task(self.player_mp_tracker.track_loop())
        
        # 3. Запускаем боевую логику выбранного класса
        self.combat_task = asyncio.create_task(self.bot_combat.start_loop())
        
        await asyncio.gather(
            self.tracker_task, 
            self.player_hp_task, 
            self.player_mp_task, 
            self.combat_task
        )

    def shutdown(self):
        print("\n[Выход] Закрытие ресурсов менеджера...")
        # Останавливаем шину кадров
        self.frame_bus.stop()
        
        # Гасим все корутины трекеров и боя
        if self.tracker_task: self.tracker_task.cancel()
        if self.player_hp_task: self.player_hp_task.cancel()
        if self.player_mp_task: self.player_mp_task.cancel()
        if self.combat_task: self.combat_task.cancel()
        
        self.buff_system.stop_buff_timers()
        try:
            keyboard.remove_all_hotkeys()
        except AttributeError:
            pass
        self.arduino.close()
        print("[Готово] Бот полностью отключен.")

