import asyncio
from arduino.arduino_controller_async import AsyncArduinoController

class BuffSystem:
    def __init__(self, arduino: AsyncArduinoController):
        """
        Класс управления автоматическим ребаффом для Овера/Варка (Основное окно).
        """
        self.arduino = arduino
        self.is_paused = False
        self.buff_tasks = []
        
        # Конфигурация групп баффов и их таймингов (в секундах)
        self.buff_schedule = [
            {"keys": ["Num1", "Num2"], "interval": 900},
            {"keys": ["Num3", "Num4"], "interval": 950},
            {"keys": ["Num5", "Num6"], "interval": 1000},
            {"keys": ["Num7", "Num8"], "interval": 1050},
            {"keys": ["Num9"],          "interval": 1100}
        ]

    async def _safe_send_button(self, button_name: str):
        """Вспомогательный метод отправки кнопки с учётом глобальной паузы."""
        while self.is_paused:
            await asyncio.sleep(0.5)
            
        print(f"[Баффер] Прожимаю бафф: {button_name}")
        await self.arduino.send_button(button_name)
        
        # УВЕЛИЧЕНО: Таймаут между баффами теперь строго 2 секунды для каста
        await asyncio.sleep(2.0)

    async def buff_all_at_start(self):
        """Фулл-бафф при старте бота (Num1 - Num9 по очереди)."""
        print("\n[Баффер] Запуск первичного фулл-баффа на старте...")
        
        all_keys = ["Num1", "Num2", "Num3", "Num4", "Num5", "Num6", "Num7", "Num8", "Num9"]
        for key in all_keys:
            await self._safe_send_button(key)
            
        print("[Баффер] Первичный фулл-бафф успешно завершён.\n")

    async def _buff_group_loop(self, group: dict):
        """Изолированный асинхронный цикл для конкретной группы баффов."""
        await asyncio.sleep(group["interval"])
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(1.0)
                    continue
                
                print(f"[Баффер] Пришло время ребаффа группы: {group['keys']}")
                
                for key in group["keys"]:
                    await self._safe_send_button(key)
                
                await asyncio.sleep(group["interval"])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Ошибка Баффера] Сбой в цикле группы {group['keys']}: {e}")
                await asyncio.sleep(2.0)

    def start_buff_timers(self):
        print("[Баффер] Активация циклических таймеров ребаффа...")
        self.buff_tasks = []
        for group in self.buff_schedule:
            task = asyncio.create_task(self._buff_group_loop(group))
            self.buff_tasks.append(task)

    def stop_buff_timers(self):
        print("[Баффер] Остановка таймеров баффов...")
        for task in self.buff_tasks:
            task.cancel()
        self.buff_tasks.clear()
