import asyncio
import numpy as np
from vision.screen_capture import ScreenCapturer

class FrameBus:
    def __init__(self, check_interval: float = 0.05):
        """
        Единая шина кадров (Shared Frame Bus).
        Исключает дублирование полноэкранных скриншотов в памяти.
        """
        self.capturer = ScreenCapturer()
        self.check_interval = check_interval
        self.trackers = []
        self._capture_task = None
        self.is_paused = False

    def register_tracker(self, tracker):
        """Регистрирует трекер для получения обновлений кадров."""
        if tracker not in self.trackers:
            self.trackers.append(tracker)

    async def _capture_loop(self):
        print("[Шина Кадров] Центральный воркер захвата экрана запущен.")
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
            try:
                # Делаем один единственный полноэкранный снимок на всю систему
                screenshot = self.capturer.take_screenshot()
                frame_np = np.array(screenshot)
                
                # Раздаем один и тот же массив всем активным трекерам шкал
                for tracker in self.trackers:
                    if not tracker.is_paused:
                        tracker.update_frame(frame_np)
                        
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"[Ошибка Шины Кадров]: {e}")
                await asyncio.sleep(1.0)

    def start(self):
        """Запускает асинхронный цикл захвата."""
        if not self._capture_task or self._capture_task.done():
            self._capture_task = asyncio.create_task(self._capture_loop())

    def stop(self):
        """Останавливает цикл захвата экрана."""
        if self._capture_task:
            self._capture_task.cancel()
            self._capture_task = None
        print("[Шина Кадров] Цикл захвата остановлен.")
