import os
import json
import numpy as np
import asyncio
from vision.screen_capture import ScreenCapturer

class StateTracker:
    def __init__(self, profile_name="PK_den4ika", check_interval=0.1, consecutive_triggers=2, mode="target_hp"):
        self.profile_name = profile_name
        self.check_interval = check_interval
        self.consecutive_triggers = consecutive_triggers
        self.mode = mode  # Варианты: "target_hp", "player_hp", "player_mp"
        
        vision_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(vision_dir), "config.json")
        
        self.start_point = None
        self.end_point = None
        self.points = []
        self.base_colors = []
        
        self.points_status = [True] * 6
        self.change_counters = {i: 0 for i in range(6)}
        
        self.capturer = ScreenCapturer()
        self.is_paused = False
        
        # Поля для единой шины кадров
        self._current_frame = None
        self._frame_event = asyncio.Event()

    def load_profile(self) -> bool:
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # Гарантируем, что имя профиля ищется строго как строка, исключая сбои маппинга JSON
            p_name = str(self.profile_name)
            profiles = config.get("profiles", {})
            
            if p_name not in profiles:
                return False
                
            profile = profiles[p_name]
            
            if self.mode == "target_hp":
                s_key, e_key = "start_point", "end_point"
            elif self.mode == "player_hp":
                s_key, e_key = "player_hp_start", "player_hp_end"
            else:
                s_key, e_key = "player_mp_start", "player_mp_end"

            if s_key in profile and e_key in profile:
                self.start_point = tuple(profile[s_key])
                self.end_point = tuple(profile[e_key])
                
                screen = self.capturer.take_screenshot()
                screen_bgr = self.capturer.get_bgr_array(screen)
                self.calculate_points(screen_bgr)
                return True
        except Exception as e:
            print(f"Ошибка чтения профиля {self.mode}: {e}")
        return False

    def calculate_points(self, current_frame):
        """
        Вычисляет 6 контрольных точек вдоль линии калибровки шкал.
        Интегрирован фикс DPI-масштабирования под физический размер кадра.
        """
        x1, y1 = self.start_point
        x2, y2 = self.end_point
        h, w, _ = current_frame.shape
        
        # --- ФИКС DPI ДЛЯ КОНТРОЛЬНЫХ ТОЧЕК ШКАЛ ---
        # Вычисляем логический размер экрана через win32api
        import win32api
        import win32con
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        
        # Рассчитываем коэффициент масштабирования Windows
        dpi_factor_x = w / screen_w
        dpi_factor_y = h / screen_h
        
        # Переводим логические координаты калибровки Tkinter в физические пиксели кадра
        x1_phys = int(x1 * dpi_factor_x)
        x2_phys = int(x2 * dpi_factor_x)
        y1_phys = int(y1 * dpi_factor_y)
        y2_phys = int(y2 * dpi_factor_y)
        
        self.points = []
        self.base_colors = []
        self.points_status = [True] * 6  
        self.change_counters = {i: 0 for i in range(6)}
        
        # 6 точек контроля: 0%, 20%, 40%, 60%, 80%, 100%
        steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        delta_x = x2_phys - x1_phys
        delta_y = y2_phys - y1_phys
        
        for i, t in enumerate(steps):
            x = int(x1_phys + delta_x * t)
            y = int(y1_phys + delta_y * t)
            
            # Защита от выхода за границы матрицы кадра
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            
            self.points.append((x, y))
            raw_bgr = current_frame[y, x]
            self.base_colors.append([int(raw_bgr[0]), int(raw_bgr[1]), int(raw_bgr[2])])

    def is_color_changed(self, c1, c2, threshold=40):
        return np.linalg.norm(np.array(c1, dtype=int) - np.array(c2, dtype=int)) > threshold

    def update_frame(self, frame_np):
        """Метод для внешней поставки кадра от BotManager."""
        self._current_frame = frame_np
        self._frame_event.set()

    def get_current_value(self) -> int:
        if not self.points_status[0]:
            return 0
        for i in range(5, -1, -1):
            if self.points_status[i]:
                return i * 20
        return 0

    def calibrate_by_mode(self, mode_type: str):
        # Передаем понятный текст подсказки в зависимости от режима шкал
        labels = {
            "target_hp": "Проведите линию шкал: ХП МОБА (Цели)",
            "player_hp": "Проведите линию шкал: ХП ВАШЕГО ПЕРСОНАЖА",
            "player_mp": "Проведите линию шкал: МП ВАШЕГО ПЕРСОНАЖА (Мана)"
        }
        title = labels.get(mode_type, "Проведите линию калибровки")
        
        p1, p2, frame_bgr = self.capturer.select_line_on_screen(title_text=title)
        # ... дальше код сохранения в json идет без изменений ...

    async def track_loop(self):
        valid_templates = [
            [False, False, False, False, False, False],
            [True,  False, False, False, False, False],
            [True,  True,  False, False, False, False],
            [True,  True,  True,  False, False, False],
            [True,  True,  True,  True,  False, False],
            [True,  True,  True,  True,  True,  False],
            [True,  True,  True,  True,  True,  True]
        ]
        
        last_log_time = 0.0
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
                
            try:
                # Ожидаем появление нового кадра в шине данных
                await self._frame_event.wait()
                self._frame_event.clear()
                
                if self._current_frame is None:
                    continue
                    
                frame_bgr = self._current_frame
                h, w, _ = frame_bgr.shape
                
                temp_status = [True] * 6
                for i, (x, y) in enumerate(self.points):
                    if y >= h or x >= w: continue
                    
                    raw_bgr = frame_bgr[y, x]
                    # ИСПРАВЛЕНИЕ: Раскладываем пиксель OpenCV строго как B, G, R
                    b, g, r = int(raw_bgr[0]), int(raw_bgr[1]), int(raw_bgr[2])
                    
                    if self.mode == "player_mp":
                        # Ищем синюю ману: синего (b) должно быть больше, чем красного (r)
                        if b > r + 30 and b > 70:
                            temp_status[i] = True
                        else:
                            temp_status[i] = False
                    elif self.mode == "player_hp" or self.mode == "target_hp":
                        # Ищем красное ХП: красного (r) должно быть больше, чем синего (b)
                        if r > b + 30 and r > 70:
                            temp_status[i] = True
                        else:
                            temp_status[i] = False
                    else:
                        if self.is_color_changed([r, g, b], self.base_colors[i]):
                            temp_status[i] = False

                if temp_status in valid_templates:
                    status_changed = False
                    
                    for i in range(6):
                        if temp_status[i] != self.points_status[i]:
                            self.change_counters[i] += 1
                            if self.change_counters[i] >= self.consecutive_triggers:
                                self.points_status[i] = temp_status[i]
                                status_changed = True
                        else:
                            self.change_counters[i] = 0
                    
                    curr_time = asyncio.get_event_loop().time()
                    if status_changed or (curr_time - last_log_time >= 1.5):
                        val = self.get_current_value()
                        visual_status = ["+" if s else "-" for s in self.points_status]
                        
                        mode_labels = {
                            "target_hp": "МОБ HP  ",
                            "player_hp": "ДВАРФ HP",
                            "player_mp": "ДВАРФ MP"
                        }
                        label = mode_labels.get(self.mode, self.mode)
                        
                        print(f"[{label}] Значение: {val}% | Точки матрицы: {visual_status}")
                        last_log_time = curr_time
                            
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"[Ошибка Трекера {self.mode}]: {e}")
                await asyncio.sleep(1.0)

    def calibrate(self):
        print("[Калибровка] Запуск калибровки ХП моба по умолчанию...")
        self.calibrate_by_mode("target_hp")
