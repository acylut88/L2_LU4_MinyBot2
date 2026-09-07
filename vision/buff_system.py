import asyncio
from arduino.arduino_controller_async import AsyncArduinoController

class BuffSystem:
    def __init__(self, arduino: AsyncArduinoController):
        """
        Класс управления автоматическим ребаффом для Овера/Варка (Основное окно).
        Синхронизирован с боевым циклом.
        """
        self.arduino = arduino
        self.is_paused = False
        self.buff_tasks = []
        
        # Очередь баффов, ожидающих безопасного момента для прожима
        self.pending_buffs = {i: False for i in range(5)}
        
        # Конфигурация групп баффов и их таймингов (в секундах)
        self.buff_schedule = [
            {"keys": ["Num1", "Num2"], "interval": 900},
            {"keys": ["Num3", "Num4"], "interval": 950},
            {"keys": ["Num5", "Num6"], "interval": 1000},
            {"keys": ["Num7", "Num8"], "interval": 1050},
            {"keys": ["Num9"],          "interval": 1100}
        ]

    async def _send_button_with_delay(self, button_name: str):
        """Прожимает кнопку баффа и жестко ждет 2 секунды окончания анимации каста."""
        print(f"[Баффер] Кастую бафф: {button_name}...")
        await self.arduino.send_button(button_name)
        await asyncio.sleep(2.0)  # Таймаут 2 секунды для каста

    async def buff_all_at_start(self):
        """Фулл-бафф при старте бота (Num1 - Num9 по очереди)."""
        print("\n[Баффер] Запуск первичного фулл-баффа на старте...")
        all_keys = ["Num1", "Num2", "Num3", "Num4", "Num5", "Num6", "Num7", "Num8", "Num9"]
        for key in all_keys:
            while self.is_paused:
                await asyncio.sleep(0.5)
            await self._send_button_with_delay(key)
        print("[Баффер] Первичный фулл-бафф успешно завершён.\n")

    async def _buff_timer_worker(self, index: int, interval: float):
        """Фоновый воркер, который просто фиксирует, что время баффа вышло."""
        await asyncio.sleep(interval)
        
        while True:
            try:
                # Если время пришло — выставляем флаг «бафф ожидает прожима»
                self.pending_buffs[index] = True
                
                # Ждем, пока боевой цикл заберет и сбросит этот флаг в False
                while self.pending_buffs[index]:
                    await asyncio.sleep(1.0)
                    
                # Как только бафф успешно лег, запускаем таймер на следующий круг
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Ошибка Баффера] Сбой таймера группы {index}: {e}")
                await asyncio.sleep(5.0)

    async def check_and_run_pending_buffs(self) -> bool:
        """
        Вызывается боевым циклом между убийствами мобов. 
        Если есть накопившиеся баффы — прожимает их, блокируя поиск мобов.
        """
        if self.is_paused:
            return False
            
        buffed_any = False
        
        # Проверяем все 5 групп по очереди
        for i, group in enumerate(self.buff_schedule):
            if self.pending_buffs[i]:
                print(f"\n[Баффер] Безопасный момент! Начинаю ребафф группы {i+1}: {group['keys']}")
                buffed_any = True
                
                # Поочередно прожимаем кнопки баффа из этой группы
                for key in group["keys"]:
                    if self.is_paused:
                        break
                    await self._send_button_with_delay(key)
                    
                # Сбрасываем флаг ожидания, воркер запустит таймер заново
                self.pending_buffs[i] = False
                print(f"[Баффер] Ребафф группы {i+1} завершен.\n")
                
        return buffed_any

    def start_buff_timers(self):
        print("[Баффер] Активация независимых таймеров ребаффа...")
        self.buff_tasks = []
        for i, group in enumerate(self.buff_schedule):
            task = asyncio.create_task(self._buff_timer_worker(i, group["interval"]))
            self.buff_tasks.append(task)

    def stop_buff_timers(self):
        print("[Баффер] Остановка таймеров баффов...")
        for task in self.buff_tasks:
            task.cancel()
        self.buff_tasks.clear()
