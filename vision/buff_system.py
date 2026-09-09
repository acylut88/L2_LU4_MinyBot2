import asyncio
from arduino.arduino_controller_async import AsyncArduinoController

class BuffSystem:
    def __init__(self, arduino: AsyncArduinoController):
        """
        Универсальный класс управления автоматическим ребаффом поддержки.
        Адаптирован под 4 числовых режима поведения саппорта на втором окне.
        """
        self.arduino = arduino
        self.is_paused = False
        self.buff_tasks = []
        self.bot_manager = None
        self.support_mode = 0  # Прилетает из BotManager (1-4)
        
        self.MODES_WITH_BUFF = [1, 2]       # Режимы с ребаффом по таймеру (1-Овер, 2-ЕЕ)
        self.MODES_WITH_RECHARGE = [2, 3]   # Режимы с заливкой маны (2-ЕЕ, 3-ШЕ)
        
        # Монолитный флаг готовности к ребаффу (индекс 0)
        self.pending_buffs = {0: False}
        
        # Расписание: 8 баффов подряд (F1-F8) раз в 19 минут (1140 секунд)
        self.buff_schedule = {
            "keys": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"],
            "interval": 1140
        }

    async def _send_button_with_delay(self, button_name: str, delay: float = 2.2):
        """Прожимает кнопку через Arduino и ждет окончания анимации каста."""
        print(f"[Саппорт] Кастую бафф: {button_name}...")
        await self.arduino.send_button(button_name)
        await asyncio.sleep(delay)

    async def buff_all_at_start(self):
        """Принудительный пати-ребафф прямо при старте бота, чтобы не идти в бой без баффов."""
        if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Dual-Box":
            if self.support_mode in self.MODES_WITH_BUFF:
                print("\n[Баффер] Первичный запуск! Начинаю принудительный стартовый пати-ребафф ЕЕ...")
                self.pending_buffs[0] = True
                await self.check_and_run_pending_buffs()
                return
            
        if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Single-Box":
            combat_profile = getattr(self.bot_manager, 'combat_profile_name', 'summoner')
            if "mage" in combat_profile.lower() or "dwarf" in combat_profile.lower():
                print("[Баффер] Одиночный режим Мага-Дварфа. Селф-баффы отсутствуют. Пропускаем старт.")
                return

        print("\n[Баффер] Запуск первичного селф-баффа на старте (Соло режим)...")
        for key in self.buff_schedule["keys"]:
            if self.is_paused: break
            await self._send_button_with_delay(key, delay=2.0)
        print("[Баффер] Первичный селф-бафф успешно завершён.\n")

    async def _buff_timer_worker(self, interval: float):
        """Фоновый воркер таймера ребаффа с защитой от зависания на паузе."""
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Время пришло — выставляем флаг
                self.pending_buffs[0] = True
                
                # Ждем сброса флага боевым циклом мейна, учитывая состояние паузы
                while self.pending_buffs[0]:
                    if self.is_paused:
                        # Если бот на паузе, приостанавливаем ожидание, чтобы не блокировать поток
                        await asyncio.sleep(2.0)
                        continue
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Ошибка Баффера] Сбой воркера таймера: {e}")
                await asyncio.sleep(5.0)

    async def check_and_run_pending_buffs(self) -> bool:
        """
        Вызывается боевым циклом мейна строго между мобами (когда ХП моба = 0).
        Оркеструет сбор пати силами мейна и ребафф.
        """
        if self.is_paused or not self.bot_manager or not self.pending_buffs.get(0, False):
            return False
            
        # СЦЕНАРИЙ 2: ЗАЛИВКА + БАФФ (ЕЕ / ШЕ)
        if self.support_mode == 2:
            print("\n[Баффер] Время баффа вышло! Запуск пати-ребаффа ЗАЛИВКИ (7 баффов)...")
            self.bot_manager.bot_combat.is_paused = True
            
            print("[Мейн] Отправляем инвайт саппорту в группу (Кнопка 'F5')...")
            await self.bot_manager.arduino.send_button("F5")
            await asyncio.sleep(0.5)
            
            if await self.bot_manager.switch_window("second"):
                keys_list = self.buff_schedule["keys"]
                for idx, key in enumerate(keys_list):
                    if self.is_paused or not self.bot_manager.bot_combat.is_paused:
                        break
                        
                    if idx == len(keys_list) - 1:
                        await self._send_button_with_delay(key, delay=4.5)
                    else:
                        await self._send_button_with_delay(key, delay=2.2)
                        
                await self.bot_manager.switch_window("main")
                
            self.pending_buffs[0] = False
            self.bot_manager.bot_combat.is_paused = False
            print("[Баффер] Пати-ребафф ЗАЛИВКИ успешно завершен.\n")
            return True
            
        # СЦЕНАРИЙ 1: ЧИСТЫЙ БАФФЕР (Овер / Варк - без пати, просто переключаем окно)
        elif self.support_mode == 1:
            print("\n[Баффер] Время баффа вышло! Запуск стандартного ребаффа БАФФЕРА...")
            self.bot_manager.bot_combat.is_paused = True
            
            if await self.bot_manager.switch_window("second"):
                for key in ["Num1", "Num2", "Num3", "Num4", "Num5"]:
                    if self.is_paused: break
                    await self._send_button_with_delay(key, delay=2.0)
                await self.bot_manager.switch_window("main")
                
            self.pending_buffs[0] = False
            self.bot_manager.bot_combat.is_paused = False
            print("[Баффер] Ребафф БАФФЕРА успешно завершен.\n")
            return True
            
        return False

    def start_buff_timers(self):
        if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Dual-Box":
            if self.support_mode in self.MODES_WITH_BUFF:
                print(f"[Баффер] Запуск фонового таймера ребаффа (Режим роли: {self.support_mode})")
                self.buff_tasks = [asyncio.create_task(self._buff_timer_worker(self.buff_schedule["interval"]))]

    def stop_buff_timers(self):
        if self.buff_tasks:
            print("[Баффер] Остановка таймеров баффов...")
            for task in self.buff_tasks:
                task.cancel()
            self.buff_tasks.clear()
