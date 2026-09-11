# version2/auto_calibrator/screen_saver.py
import os
import asyncio
from datetime import datetime
from PIL import ImageGrab

class ScreenSaver:
    def __init__(self, core):
        self.core = core
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ss_dir = os.path.join(self.base_dir, "screenshots")
        
        # Создаем папку для скриншотов фармера
        os.makedirs(self.ss_dir, exist_ok=True)

    def save_snapshot(self, trigger_name: str):
        """Мгновенно делает снимок всех экранов и сохраняет на диск."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{trigger_name}_{timestamp}.png"
            full_path = os.path.join(self.ss_dir, filename)
            
            # Делаем и сохраняем скриншот
            screenshot = ImageGrab.grab(all_screens=True)
            screenshot.save(full_path)
            
            # Пишем лог события
            self.core.logger.log_event("SCREENSHOT", f"Сохранен снимок экрана: {filename}")
        except Exception as e:
            print(f"[Ошибка Скриншотера] Не удалось записать кадр: {e}")

    async def hourly_screenshot_worker(self):
        """Фоновый асинхронный поток для ежечасных скриншотов."""
        print("[Скриншотер] Фоновый часовой воркер успешно запущен.")
        while True:
            # Ждем ровно 1 час (3600 секунд)
            await asyncio.sleep(3600)
            if not self.core.is_paused:
                self.save_snapshot("hourly")
