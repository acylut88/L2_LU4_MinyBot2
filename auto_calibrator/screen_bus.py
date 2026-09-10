# auto_calibrator/screen_bus.py
"""
отвечает за непрерывное чтение экрана и обновление состояния шкал.
"""


import asyncio
import numpy as np
from PIL import ImageGrab


class ScreenBus:
    def __init__(self, calibrator_data, combat_profile):
        self.calibrator_data = calibrator_data
        self.combat_profile = combat_profile
        self.is_paused = False
        
        # Наше единое глобальное состояние шкал
        self.states = {
            "mob_hp": "0% (МЕРТВ)",
            "player_cp": "100%", "player_hp": "100%", "player_mp": "100%",
            "summon_hp": "100%", "summon_mp": "100%"
        }

    def _parse_bar(self, img_np, start_pt, end_pt, bar_type):
        x1, y1 = start_pt
        x2, y2 = end_pt
        h, w, _ = img_np.shape
        steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        active_count = 0
        
        for t in steps:
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            r, g, b = img_np[y, x]
            
            if bar_type == "mp" and (b > r + 20 and b > g + 20 and b > 60): active_count += 1
            elif bar_type == "hp" and (r > b + 25 and r > g + 25 and r > 60): active_count += 1
            elif bar_type == "cp" and (r > b + 40 and g > b + 20 and r > 100): active_count += 1
            
        if active_count == 6: return "100%"
        if active_count == 5: return "80-100%"
        if active_count == 4: return "60-80%"
        if active_count == 3: return "40-60%"
        if active_count == 2: return "20-40%"
        if active_count == 1: return "1-20%"
        return "0% (МЕРТВ)"

    async def start_loop(self):
        profiles = self.calibrator_data.get("calibrated_profiles", {})
        has_summon = self.combat_profile.get("features_flags", {}).get("use_summon_logic", False)
        
        tasks = [
            ("target_mob", "hp", "mob_hp"),
            ("player_status", "cp", "player_cp"),
            ("player_status", "hp", "player_hp"),
            ("player_status", "mp", "player_mp")
        ]
        if has_summon:
            tasks.extend([("summon_status", "hp", "summon_hp"), ("summon_status", "mp", "summon_mp")])

        print("[Шина Кадров] Поток непрерывного сканирования экрана запущен.")
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
            try:
                screenshot = ImageGrab.grab(all_screens=True)
                img_np = np.array(screenshot)
                
                for zone, bar, state_key in tasks:
                    zone_data = profiles.get(zone, {})
                    start_pt = zone_data.get(f"{bar}_start")
                    end_pt = zone_data.get(f"{bar}_end")
                    if start_pt and end_pt:
                        self.states[state_key] = self._parse_bar(img_np, start_pt, end_pt, bar)
                
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"[Ошибка Шины Кадров]: {e}")
                await asyncio.sleep(1.0)
