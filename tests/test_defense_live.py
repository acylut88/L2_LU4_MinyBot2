# tests/test_defense_live.py
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
    # СИНХРОНИЗАЦИЯ: заходим в calibrated_profiles -> player_status единого конфига
    return data["calibrated_profiles"]["player_status"]

def parse_hp_bar(img_np, start_pt, end_pt):
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
        
        # Безопасное приведение типов int для обхода uint8 overflow
        r, g, b = map(int, img_np[y, x])
        if r > b + 25 and r > g + 25 and r > 60:
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
    
    # Инициализируем плату Leonardo по нашему единому файлу
    arduino = AsyncArduinoController(config_path=config_path)
    print("[Тест] Подключение к Arduino Leonardo...")
    if not await arduino.connect():
        print("[Ошибка] Не удалось открыть COM-порт!")
        return

    # Загружаем монолитные координаты ХП
    pts = load_calibrator_points()
    hp_start, hp_end = pts["hp_start"], pts["hp_end"]
    
    last_pot_time = 0.0
    pot_cooldown = 15.0 # Кулдаун большой банки 15 секунд (Пункт 14 ТЗ)
    
    print("\n" + "="*60)
    print("   ТЕСТ АППАРАТНОЙ ЗАЩИТЫ БАНКАМИ HP (Кнопка '11')   ")
    print("=" * 60)

    try:
        while True:
            screenshot = ImageGrab.grab(all_screens=True)
            img_np = np.array(screenshot)
            
            current_hp = parse_hp_bar(img_np, hp_start, hp_end)
            print(f"[Defense Live] Моё ХП в игре: {current_hp:<10}")
            
            # Если ХП упало ниже 80% (ушло из зон 100% и 80-100%)
            if current_hp in ["1-20%", "20-40%", "40-60%", "60-80%"]:
                now = time.time()
                if now - last_pot_time >= pot_cooldown:
                    print(f"\n[ЗАЩИТА!] Обнаружен прог ХП ({current_hp}). Прожимаем банку через Ардуино...")
                    await arduino.send_button("-") # Жмет кнопку 11 из карты config.json (символ 'K')
                    last_pot_time = now
                    print(f"[Кулдаун] Запуск таймера защиты на {pot_cooldown} секунд.\n")
                    
            await asyncio.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[Тест] Успешно завершен.")
    finally:
        arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
