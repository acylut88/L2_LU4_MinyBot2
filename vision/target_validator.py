import cv2
import json
import os
import numpy as np
import asyncio
from vision.screen_capture import ScreenCapturer

try:
    from ctypes import windll
    windll.user32.SetProcessDPIAware()
except Exception as e:
    print("DPI Awareness предупреждение:", e)

class TargetValidator:
    def __init__(self, profile_name="PK_den4ika", skull_template_name="skull.png", threshold=0.75):
        self.profile_name = profile_name
        self.threshold = threshold
        
        vision_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(vision_dir), "config.json")
        self.skull_path = os.path.join(vision_dir, skull_template_name)
        
        self.bbox = None  
        self.capturer = ScreenCapturer()
        self.skull_img = self._load_template()

    def _load_template(self):
        if os.path.exists(self.skull_path):
            print("Шаблон черепа успешно загружен:", self.skull_path)
            return cv2.imread(self.skull_path, cv2.IMREAD_GRAYSCALE)
        else:
            print("Внимание! Иконка босса не найдена по пути:", self.skull_path)
            return None

    def load_profile(self) -> bool:
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            bbox = config.get("target_zones", {}).get(self.profile_name)
            if bbox:
                self.bbox = tuple(bbox)
                print("Координаты зоны цели загружены:", self.bbox)
                return True
            return False
        except Exception as e:
            print("Ошибка при чтении профиля цели:", e)
            return False

    def _save_profile(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = {}
        if "target_zones" not in config:
            config["target_zones"] = {}
        config["target_zones"][self.profile_name] = list(self.bbox)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def calibrate_target_zone(self):
        import tkinter as tk
        from PIL import ImageTk
        
        print("Делаем снимок экрана для калибровки...")
        import time
        time.sleep(1)
        screenshot = self.capturer.take_screenshot()
        
        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        canvas = tk.Canvas(root, cursor="cross", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        tk_img = ImageTk.PhotoImage(screenshot)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        
        start_x, start_y = 0, 0
        rect_id = None
        
        def on_press(event):
            nonlocal start_x, start_y, rect_id
            start_x, start_y = event.x, event.y
            if rect_id: canvas.delete(rect_id)
        def on_drag(event):
            nonlocal rect_id
            if rect_id: canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x, start_y, event.x, event.y, outline="yellow", width=2)
        def on_release(event):
            x = min(start_x, event.x)
            y = min(start_y, event.y)
            w = abs(event.x - start_x)
            h = abs(event.y - start_y)
            self.bbox = (x, y, w, h)
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.mainloop()
        
        if self.bbox and self.bbox[2] > 5 and self.bbox[3] > 5:
            self._save_profile()
        else:
            raise ValueError("Область цели не была выделена корректно!")

    def _sync_match_template(self, screenshot):
        frame_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        x, y, w, h = self.bbox
        roi = frame_gray[y:y+h, x:x+w]
        
        if roi.shape[0] < self.skull_img.shape[0] or roi.shape[1] < self.skull_img.shape[1]:
            return False

        result = cv2.matchTemplate(roi, self.skull_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        
        return max_val >= self.threshold

    async def is_boss_selected(self) -> bool:
        if self.skull_img is None or not self.bbox:
            return False

        loop = asyncio.get_event_loop()
        screenshot = await loop.run_in_executor(None, self.capturer.take_screenshot)
        is_boss = await loop.run_in_executor(None, self._sync_match_template, screenshot)
        
        return is_boss
