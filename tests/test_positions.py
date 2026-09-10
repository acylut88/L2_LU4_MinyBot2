import os
import json
import time
import numpy as np
import tkinter as tk
from PIL import ImageDraw, ImageFont
from vision.screen_capture import ScreenCapturer

def run_diagnostic_test():
    print("=" * 60)
    print("   ДИАГНОСТИКА: ТЕСТ КООРДИНАТ + RGB + МАТРИЦЫ СИСТЕМЫ В КОНСОЛЬ   ")
    print("=" * 60)

    config_path = "config.json"
    if not os.path.exists(config_path):
        print(f"[Ошибка] Не найден файл конфигурации '{config_path}' в корне проекта!")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    profiles = config.get("profiles", {})
    if not profiles:
        print("[Ошибка] В вашем конфиге нет ни одного профиля разметки шкал!")
        return

    print("\nДоступные профили в конфиге:")
    profile_keys = list(profiles.keys())
    for idx, p in enumerate(profile_keys, 1):
        print(f"  {idx}. {p}")
        
    p_choice = input("\nВведите ИМЯ профиля или его НОМЕР для проверки: ").strip()
    
    if p_choice.isdigit():
        idx = int(p_choice) - 1
        if 0 <= idx < len(profile_keys):
            p_choice = profile_keys[idx]
            print(f"[Инфо] Автоматически выбран профиль: '{p_choice}'")

    if p_choice not in profiles:
        print(f"[Ошибка] Профиль '{p_choice}' не найден in config.json!")
        return

    profile = profiles[p_choice]

    print("\nИнструкция:")
    print("1. Разверните окно Lineage 2.")
    print("2. Подготовьте шкалы (цель, селф ХП/МП должны быть на экране).")
    print("3. У вас есть 4 секунды до захвата кадра...")
    
    for i in range(4, 0, -1):
        print(f"Захват через {i}...")
        time.sleep(1.0)

    print("\n[Захват] Делаем тестовый снимок экрана...")
    capturer = ScreenCapturer()
    screenshot = capturer.take_screenshot()
    
    frame_rgb = np.array(screenshot)
    img_draw = screenshot.convert("RGB")
    draw = ImageDraw.Draw(img_draw)

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except IOError:
        font = ImageFont.load_default()

    img_w, img_h = screenshot.size
    
    root = tk.Tk()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.destroy()

    print(f"\n[DPI Дебаг] Физический размер снимка: {img_w}x{img_h}")
    print(f"[DPI Дебаг] Логическая сетка Windows:  {screen_w}x{screen_h}")
    
    dpi_factor_x = img_w / screen_w
    dpi_factor_y = img_h / screen_h

    modes = {
        "target_hp": {
            "name": "МОБ HP (ЦЕЛЬ)",
            "keys": ("start_point", "end_point"),
            "color": (255, 0, 0)
        },
        "player_hp": {
            "name": "ДВАРФ HP (СЕЛФ)",
            "keys": ("player_hp_start", "player_hp_end"),
            "color": (255, 128, 0)
        },
        "player_mp": {
            "name": "ДВАРФ MP (МАНА)",
            "keys": ("player_mp_start", "player_mp_end"),
            "color": (0, 128, 255)
        }
    }

    steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    for mode_type, settings in modes.items():
        s_key, e_key = settings["keys"]
        color = settings["color"]
        mode_label = settings["name"]
        
        if s_key not in profile or e_key not in profile:
            continue
            
        x1, y1 = profile[s_key]
        x2, y2 = profile[e_key]

        print(f"\n" + "-"*75)
        print(f" АНАЛИЗ СЕТКИ И ПОРОГОВ ДЛЯ ШКАЛЫ: {mode_label}")
        print(f" Линия из конфига: [{x1}, {y1}] -> [{x2}, {y2}]")
        print(f"-"*75)
        print(f"{'Точка':<6} | {'Чистый Режим (БЕЗ DPI)':<24} | {'Режим С DPI Масштабом':<24}")
        print(f"{'':<6} | {'Коорд':<9} {'Цвет':<11} {'Тест':<2} | {'Коорд':<9} {'Цвет':<11} {'Тест':<2}")
        print(f"_"*75)

        # 1. Расчет для чистого режима
        delta_x = x2 - x1
        delta_y = y2 - y1
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

        # 2. Расчет для DPI режима
        x1_phys = int(x1 * dpi_factor_x)
        x2_phys = int(x2 * dpi_factor_x)
        y1_phys = int(y1 * dpi_factor_y)
        y2_phys = int(y2 * dpi_factor_y)
        delta_x_phys = x2_phys - x1_phys
        delta_y_phys = y2_phys - y1_phys

        # Массивы сбора итоговых матриц (+/-) для вывода под таблицей
        clean_matrix = []
        dpi_matrix = []

        for idx, t in enumerate(steps):
            pct = f"{int(t*100)}%"
            
            # --- ВЫЧИСЛЕНИЕ ДЛЯ ЧИСТОГО РЕЖИМА ---
            x = max(0, min(int(x1 + delta_x * t), img_w - 1))
            y = max(0, min(int(y1 + delta_y * t), img_h - 1))
            rgb_raw = frame_rgb[y, x]
            r, g, b = int(rgb_raw[0]), int(rgb_raw[1]), int(rgb_raw[2])
            
            # Применяем цветовой фильтр из стабильного ядра ветки main
            is_valid_clean = False
            if mode_type == "player_mp":
                if b > r + 30 and b > 70: is_valid_clean = True
            else: # player_hp или target_hp
                if r > b + 30 and r > 70: is_valid_clean = True
            
            c_mark = "+" if is_valid_clean else "-"
            clean_matrix.append(c_mark)

            # --- ВЫЧИСЛЕНИЕ ДЛЯ DPI РЕЖИМА ---
            x_p = max(0, min(int(x1_phys + delta_x_phys * t), img_w - 1))
            y_p = max(0, min(int(y1_phys + delta_y_phys * t), img_h - 1))
            rgb_p = frame_rgb[y_p, x_p]
            r_p, g_p, b_p = int(rgb_p[0]), int(rgb_p[1]), int(rgb_p[2])
            
            is_valid_dpi = False
            if mode_type == "player_mp":
                if b_p > r_p + 30 and b_p > 70: is_valid_dpi = True
            else:
                if r_p > b_p + 30 and r_p > 70: is_valid_dpi = True
                
            d_mark = "+" if is_valid_dpi else "-"
            dpi_matrix.append(d_mark)

            # Форматируем строки таблицы
            c_coord = f"[{x},{y}]"
            c_rgb = f"{r},{g},{b}"
            d_coord = f"[{x_p},{y_p}]"
            d_rgb = f"{r_p},{g_p},{b_p}"
            
            print(f"{pct:<6} | {c_coord:<9} {c_rgb:<11} [{c_mark}]  | {d_coord:<9} {d_rgb:<11} [{d_mark}]")

            # Отрисовка кружков на результирующем PNG
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], outline=color, width=1)
            draw.text((x + 6, y - 6), pct, fill=color, font=font)
            draw.ellipse([x_p - 3, y_p - 3, x_p + 3, y_p + 3], fill=color)
            draw.text((x_p + 6, y_p + 6), f"{pct}DPI", fill=(255, 255, 255), font=font)

        # Вывод итоговой кумулятивной матрицы, как её увидит StateTracker.get_current_value()
        def calc_pct(m):
            true_count = sum(1 for x in m if x == "+")
            return int((true_count / 6) * 100)
            
        print(f"¯"*75)
        print(f"[ИТОГ БЕЗ DPI]: Матрица {clean_matrix} -> Процент шкалы: {calc_pct(clean_matrix)}%")
        print(f"[ИТОГ С DPI ]: Матрица {dpi_matrix} -> Процент шкалы: {calc_pct(dpi_matrix)}%")

    result_filename = "test_positions_result.png"
    img_draw.save(result_filename, "PNG")
    print(f"\n[Успех] Диагностический снимок сохранен в: '{result_filename}'")
    
    try:
        os.startfile(result_filename)
    except Exception:
        pass

if __name__ == "__main__":
    run_diagnostic_test()
