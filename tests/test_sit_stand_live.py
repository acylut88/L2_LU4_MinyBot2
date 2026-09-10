# tests/test_sit_stand_live.py
import os
import sys
import json
import time
import asyncio
import numpy as np
from PIL import ImageGrab

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from version2.arduino.arduino_controller_async import AsyncArduinoController

def load_calibrator_points():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "version2", "config.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["calibrated_profiles"]["player_status"]

def parse_mp_bar(img_np, start_pt, end_pt):
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
        
        r, g, b = map(int, img_np[y, x])
        if b > r + 20 and b > g + 20 and b > 60:
            active_count += 1
            
    if active_count == 6: return "100%"
    if active_count == 5: return "80-100%"
    if active_count == 4: return "60-80%"
    if active_count == 3: return "40-60%"
    if active_count == 2: return "20-40%"
    if active_count == 1: return "1-20%"
    return "0% (МЕРТВ)"

async def main():
    try:
        from ctypes import windll
        windll.user32.SetProcessDPIAware()
    except: pass

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "version2", "config.json")
    
    arduino = AsyncArduinoController(config_path=config_path)
    print("[Тест] Подключение к Arduino Leonardo...")
    if not await arduino.connect():
        print("[Ошибка] Не удалось открыть COM-порт!")
        return

    # Загружаем монолитные координаты
    pts = load_calibrator_points()
    mp_start, mp_end = pts["mp_start"], pts["mp_end"]
    
    is_sitting = False
    sit_time = 0.0
    
    print("\n" + "="*60)
    print("   ТЕСТ АППАРАТНОЙ ПОСАДКИ ПО ЕДИНОМУ СИНХРОННОМУ КОНФИГУ   ")
    print("=" * 60)

    try:
        while True:
            screenshot = ImageGrab.grab(all_screens=True)
            img_np = np.array(screenshot)
            
            current_mp = parse_mp_bar(img_np, mp_start, mp_end)
            print(f"[Live] Мана в игре: {current_mp:<10} | Сидим: {is_sitting}")
            
            if not is_sitting:
                if current_mp in ["0% (МЕРТВ)", "1-20%"]:
                    print("\n[Триггер] МП упало! Отправка аппаратного сигнала СЕСТЬ (Num*)...")
                    await arduino.send_button("Num*")
                    is_sitting = True
                    sit_time = time.time()
                    await asyncio.sleep(2.0)
            else:
                if current_mp in ["80-100%", "100%"] and (time.time() - sit_time >= 5.0):
                    print("\n[Триггер] МП восстановилось! Отправка аппаратного сигнала ВСТАТЬ (Num*)...")
                    await arduino.send_button("Num*")
                    is_sitting = False
                    await asyncio.sleep(2.0)
                    
            await asyncio.sleep(0.15)
            
    except KeyboardInterrupt:
        print("\n[Тест] Успешно завершен.")
    finally:
        arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
