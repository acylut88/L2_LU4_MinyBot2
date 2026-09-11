# version2/auto_calibrator/bot_logger.py
import os
from datetime import datetime
import asyncio

class BotLogger:
    def __init__(self, log_name="bot_events.log"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_path = os.path.join(self.base_dir, log_name)
        
        # Пересоздаем или очищаем лог при каждом новом запуске бота
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"=== ЗАПУСК СЕССИИ ФАРМА: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    def log_event(self, event_type: str, message: str):
        """Синхронный метод для быстрой записи критических моментов без задержек."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{event_type.upper()}] {message}\n"
        
        # Пишем в консоль для наглядности
        print(f"!!! {log_line.strip()} !!!")
        
        # Записываем в файл на диск
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"[Ошибка Логгера] Не удалось записать в файл: {e}")
