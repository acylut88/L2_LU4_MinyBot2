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
        
        # Теперь точек 6, изначально все True (считаем полоску полной)
        self.points_status = [True] * 6
        self.change_counters = {i: 0 for i in range(6)}
        
        self.capturer = ScreenCapturer()
        self.is_paused = False

    def load_profile(self) -> bool:
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            profile = config.get("profiles", {}).get(self.profile_name, {})
            
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
            print(f"Ошибка чтения профиля {self.mode}:", e)
        return False

    def calculate_points(self, current_frame):
        x1, y1 = self.start_point
        x2, y2 = self.end_point
        h, w, _ = current_frame.shape
        
        self.points = []
        self.base_colors = []
        self.points_status = [True] * 6  
        self.change_counters = {i: 0 for i in range(6)}
        
        # Строго 6 точек: 0%, 20%, 40%, 60%, 80%, 100%
        steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        delta_x = x2 - x1
        delta_y = y2 - y1
        
        for i, t in enumerate(steps):
            x = int(x1 + delta_x * t)
            y = int(y1 + delta_y * t)
            
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            
            self.points.append((x, y))
            raw_bgr = current_frame[y, x]
            self.base_colors.append([int(raw_bgr[0]), int(raw_bgr[1]), int(raw_bgr[2])])

    def is_color_changed(self, c1, c2, threshold=40):
        return np.linalg.norm(np.array(c1, dtype=int) - np.array(c2, dtype=int)) > threshold

    def get_current_value(self) -> int:
        """Расчет процентов по 6 точкам контроля."""
        # Если даже самая первая точка (0%) изменила цвет — значит шкала абсолютно пуста (0%)
        if not self.points_status[0]:
            return 0
            
        # Проверяем заполненность справа налево
        for i in range(5, -1, -1):
            if self.points_status[i]:
                return i * 20
        return 0

    def calibrate_by_mode(self, mode_type: str):
        p1, p2, frame_bgr = self.capturer.select_line_on_screen()
        
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        profiles = config.setdefault("profiles", {})
        profile = profiles.setdefault(self.profile_name, {})
        
        if mode_type == "target_hp":
            profile["start_point"] = list(p1)
            profile["end_point"] = list(p2)
        elif mode_type == "player_hp":
            profile["player_hp_start"] = list(p1)
            profile["player_hp_end"] = list(p2)
        elif mode_type == "player_mp":
            profile["player_mp_start"] = list(p1)
            profile["player_mp_end"] = list(p2)
            
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        print(f"[Калибровка] Данные для шкалы '{mode_type}' успешно записаны в '{self.profile_name}'.")

    async def track_loop(self):
        # Валидные монолитные шкалы для 6 точек контроля
        valid_templates = [
            [False, False, False, False, False, False], # 0%
            [True,  False, False, False, False, False], # 20%
            [True,  True,  False, False, False, False], # 40%
            [True,  True,  True,  False, False, False], # 60%
            [True,  True,  True,  True,  False, False], # 80%
            [True,  True,  True,  True,  True,  False], # 100% (срез)
            [True,  True,  True,  True,  True,  True]   # 100% (фулл)
        ]
        
        last_log_time = 0.0
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
            try:
                screenshot = self.capturer.take_screenshot()
                frame_rgb = np.array(screenshot)
                h, w, _ = frame_rgb.shape
                
                temp_status = [True] * 6
                for i, (x, y) in enumerate(self.points):
                    if y >= h or x >= w: continue
                    
                    raw_rgb = frame_rgb[y, x]
                    r, g, b = int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2])
                    
                    # ИНТЕЛЛЕКТУАЛЬНЫЙ АНАЛИЗ ЦВЕТА ШКАЛЫ
                    if self.mode == "player_mp":
                        if b > r + 30 and b > 70:
                            temp_status[i] = True
                        else:
                            temp_status[i] = False
                            
                    elif self.mode == "player_hp" or self.mode == "target_hp":
                        if r > b + 30 and r > 70:
                            temp_status[i] = True
                        else:
                            temp_status[i] = False
                    else:
                        if self.is_color_changed([r, g, b], self.base_colors[i]):
                            temp_status[i] = False

                # Проверка шаблона на "рваный мусор" (цифры критов и урона)
                if temp_status in valid_templates:
                    status_changed = False
                    
                    # Применяем фильтр consecutive_triggers для каждой из 6 точек
                    for i in range(6):
                        if temp_status[i] != self.points_status[i]:
                            self.change_counters[i] += 1
                            if self.change_counters[i] >= self.consecutive_triggers:
                                self.points_status[i] = temp_status[i]
                                status_changed = True
                        else:
                            self.change_counters[i] = 0
                    
                    # === ВОЗВРАЩАЕМ ТАБЛИЧКУ ДЕБАГА В КОНСОЛЬ ===
                    curr_time = asyncio.get_event_loop().time()
                    if status_changed or (curr_time - last_log_time >= 1.5):
                        val = self.get_current_value()
                        # Переводим True/False в наглядные символы + и -
                        visual_status = ["+" if s else "-" for s in self.points_status]
                        
                        # Красивое имя для вывода в консоль
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


    def get_current_hp(self) -> int:
        """Фолбэк-метод для совместимости со старыми боевыми профилями (Овер/Суммонер)."""
        return self.get_current_value()

    def calibrate(self):
        """Фолбэк-метод калибровки по умолчанию, если вызван старый метод инициализации."""
        print("[Калибровка] Запуск калибровки ХП моба по умолчанию...")
        self.calibrate_by_mode("target_hp")