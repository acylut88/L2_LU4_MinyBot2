# tests/test_bars_live.py
import os
import json
import time
import sys
import numpy as np
from PIL import ImageGrab

def load_config(config_name="config_v2.json") -> dict:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, config_name)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"[Ошибка] Файл конфигурации {config_name} не найден!")
    sys.exit(1)

def check_bar_points(img_np, start_pt, end_pt, bar_type):
    """
    Проверяет 6 точек на линии и вычисляет диапазон процентов здоровья/маны.
    """
    x1, y1 = start_pt
    x2, y2 = end_pt
    h, w, _ = img_np.shape

    steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    points_status = []
    
    for t in steps:
        x = int(x1 + (x2 - x1) * t)
        y = int(y1 + (y2 - y1) * t)
        
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        
        r, g, b = img_np[y, x]
        
        if bar_type == "mp":
            is_active = (b > r + 20 and b > g + 20 and b > 60)
        elif bar_type == "hp":
            is_active = (r > b + 25 and r > g + 25 and r > 60)
        elif bar_type == "cp":
            is_active = (r > b + 40 and g > b + 20 and r > 100)
        else:
            is_active = False
            
        points_status.append(is_active)

    # Подсчитываем количество горящих точек [+]
    active_count = sum(1 for pt in points_status if pt)

    # === РЕАЛИЗАЦИЯ ЛОГИКИ ДИАПАЗОНОВ ===
    if active_count == 6:
        percent_str = "100%"
    elif active_count == 5:
        percent_str = "80-100%"
    elif active_count == 4:
        percent_str = "60-80%"
    elif active_count == 3:
        percent_str = "40-60%"
    elif active_count == 2:
        percent_str = "20-40%"
    elif active_count == 1:
        percent_str = "1-20%"  # Исправлено: теперь это не 0%, моб еще жив!
    else:
        percent_str = "0% (МЕРТВ)" # Железно умер, все точки погасли

    return points_status, percent_str

def main():
    config = load_config()
    profiles = config.get("calibrated_profiles", {})
    has_summon = config.get("game_windows", {}).get("has_summon", False)
    
    if not profiles:
        print("[Ошибка] В конфиге нет откалиброванных профилей шкал.")
        return

    try:
        from ctypes import windll
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    tasks = [
        ("target_mob", "hp", "МОБ HP  "),
        ("player_status", "cp", "ИГРОК CP"),
        ("player_status", "hp", "ИГРОК HP"),
        ("player_status", "mp", "ИГРОК MP"),
    ]
    
    if has_summon:
        tasks.append(("summon_status", "hp", "ПЕТ HP  "))
        tasks.append(("summon_status", "mp", "ПЕТ MP  "))

    try:
        while True:
            screenshot = ImageGrab.grab(all_screens=True)
            img_np = np.array(screenshot)

            output_lines = []
            
            for zone, bar, label in tasks:
                zone_data = profiles.get(zone, {})
                start_pt = zone_data.get(f"{bar}_start")
                end_pt = zone_data.get(f"{bar}_end")
                
                if start_pt and end_pt:
                    status_list, percent_text = check_bar_points(img_np, start_pt, end_pt, bar)
                    visual_dots = " ".join(["[+]" if s else "[-]" for s in status_list])
                    
                    # Красивое выравнивание вывода по ширине строки процентов
                    output_lines.append(f"[{label}] {percent_text:<10} | Точки: {visual_dots}")
                else:
                    output_lines.append(f"[{label}] Не откалиброван в config_v2.json")

            sys.stdout.write("\033[H\033[J")
            sys.stdout.write("=== ТЕКУЩИЙ СТАТУС ПОЛОС В ИГРЕ (ОБНОВЛЕНИЕ НАЛЕТУ) ===\n\n")
            sys.stdout.write("\n".join(output_lines) + "\n")
            sys.stdout.flush()
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[Тест] Живой мониторинг успешно остановлен.")

if __name__ == "__main__":
    main()
