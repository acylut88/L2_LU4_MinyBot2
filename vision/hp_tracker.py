import os
import json
import numpy as np
import asyncio
from vision.screen_capture import ScreenCapturer

class HPTracker:
    def __init__(self, profile_name="PK_den4ika", check_interval=1.0, consecutive_triggers=3):
        self.profile_name = profile_name
        self.check_interval = check_interval
        self.consecutive_triggers = consecutive_triggers
        
        vision_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(vision_dir), "config.json")
        
        self.start_point = None
        self.end_point = None
        self.points = []
        self.base_colors = []
        self.points_status = []
        self.change_counters = {}
        self.capturer = ScreenCapturer()

    def load_profile(self):
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            profile = config.get("profiles", {}).get(self.profile_name)
            if profile and "start_point" in profile and "end_point" in profile:
                self.start_point = tuple(profile["start_point"])
                self.end_point = tuple(profile["end_point"])
                
                screen = self.capturer.take_screenshot()
                screen_bgr = self.capturer.get_bgr_array(screen)
                self.calculate_points(screen_bgr)
                return True
        except Exception as e:
            print("Ошибка чтения профиля:", e)
        return False

    def save_profile(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        if "profiles" not in config:
            config["profiles"] = {}
            
        config["profiles"][self.profile_name] = {
            "start_point": list(self.start_point),
            "end_point": list(self.end_point)
        }
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def calculate_points(self, current_frame):
        x1, y1 = self.start_point
        x2, y2 = self.end_point
        h, w, _ = current_frame.shape
        
        self.points = []
        self.base_colors = []
        self.points_status = [True] * 5  
        self.change_counters = {i: 0 for i in range(5)}
        
        steps = [0.1, 0.3, 0.5, 0.7, 0.9]
        delta_x = x2 - x1
        delta_y = y2 - y1
        
        for i, t in enumerate(steps):
            x = int(x1 + delta_x * t)
            y = int(y1 + delta_y * t)
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            
            self.points.append((x, y))
            raw_bgr = current_frame[y, x]
            color_rgb = [int(raw_bgr[2]), int(raw_bgr[1]), int(raw_bgr[0])]
            self.base_colors.append(color_rgb)
            
        print(f"5 контрольных точек для {self.profile_name} успешно инициализированы.")

    def calibrate(self):
        p1, p2, frame_bgr = self.capturer.select_line_on_screen()
        self.start_point = p1
        self.end_point = p2
        self.calculate_points(frame_bgr)
        self.save_profile()

    def is_color_changed(self, c1, c2, threshold=40):
        return np.linalg.norm(np.array(c1, dtype=int) - np.array(c2, dtype=int)) > threshold

    def get_current_hp(self):
        for i in range(4, -1, -1):
            if self.points_status[i]:
                return (i + 1) * 20
        return 0

    async def track_loop(self):
        print(f"Старт скоростного мониторинга для [{self.profile_name}] БЕЗ дебаг-файлов.")
        last_log_time = 0.0
        
        try:
            while True:
                screenshot = self.capturer.take_screenshot()
                frame_rgb = np.array(screenshot)
                h, w, _ = frame_rgb.shape
                
                status_changed = False
                
                for i, (x, y) in enumerate(self.points):
                    if y >= h or x >= w:
                        continue
                        
                    raw_rgb = frame_rgb[y, x]
                    curr_color = [int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2])]
                    base_color = self.base_colors[i]
                    
                    changed = self.is_color_changed(curr_color, base_color)
                    
                    if changed:
                        self.change_counters[i] += 1
                        if self.change_counters[i] >= self.consecutive_triggers:
                            if self.points_status[i]:
                                self.points_status[i] = False
                                status_changed = True
                    else:
                        self.change_counters[i] = 0
                        if not self.points_status[i]:
                            self.points_status[i] = True
                            status_changed = True
                            
                curr_time = asyncio.get_event_loop().time()
                
                if status_changed or (curr_time - last_log_time >= 1.0):
                    hp = self.get_current_hp()
                    visual_status = ["+" if s else "-" for s in self.points_status]
                    print(f"[{self.profile_name} HP] Здоровье: {hp}% | Точки: {visual_status}")
                    last_log_time = curr_time
                    
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            print("Мониторинг ХП остановлен.")
