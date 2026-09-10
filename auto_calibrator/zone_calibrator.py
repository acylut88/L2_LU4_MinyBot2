# auto_calibrator/zone_analyzer.py
import os
import json
import cv2
import numpy as np

class ZoneAnalyzer:
    def __init__(self, config_name="config_v2.json"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.folder_dir = os.path.join(self.base_dir, "auto_calibrator")
        self.debug_dir = os.path.join(self.folder_dir, "debug_images")
        self.config_path = os.path.join(self.base_dir, config_name)
        
        self.config_data = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"raw_zones": {}, "calibrated_profiles": {}, "game_windows": {"has_summon": False}}

    def _save_config(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def find_bar_by_color(self, img_bgr, bar_type="hp"):
        """
        Умный поиск полосы: определяет высоту полосы по вертикали 
        и выбирает горизонтальный срез в обход белого текста цифр.
        """
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # Точные маски под современный интерфейс L2 (учитывая легкий градиент)
        if bar_type == "hp":
            # Бордово-красный цвет HP
            lower1 = np.array([0, 100, 50])
            upper1 = np.array([10, 255, 200])
            lower2 = np.array([165, 100, 50])
            upper2 = np.array([180, 255, 200])
            mask1 = cv2.inRange(hsv, lower1, upper1)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
        elif bar_type == "mp":
            # Насыщенный синий цвет MP
            lower = np.array([100, 120, 100])
            upper = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif bar_type == "cp":
            # Желто-оранжевый цвет CP
            lower = np.array([15, 150, 150])
            upper = np.array([25, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        else:
            return None

        # 1. Считаем количество целевых пикселей в каждой строке (по вертикали)
        row_counts = np.sum(mask > 0, axis=1)
        
        # Находим все строки, где полоса присутствует (хотя бы 30% от ширины кропа)
        valid_rows = np.where(row_counts > (img_bgr.shape[1] * 0.3))[0]
        
        if len(valid_rows) == 0:
            return None
            
        # Определяем верхнюю и нижнюю границы конкретной полосы
        top_y = valid_rows[0]
        bottom_y = valid_rows[-1]
        bar_height = bottom_y - top_y
        
        if bar_height < 4: # Слишком узкая область — скорее всего шум
            return None

        # 2. ОБХОД ТЕКСТА: Цифры всегда по центру полосы. 
        # Берем срез в нижней четверти полосы (на 2 пикселя выше её физического дна)
        best_y = int(bottom_y - 2)
        
        # 3. Находим реальное начало и конец полосы по Х на этой чистой строке
        filled_indices = np.where(mask[best_y] > 0)[0]
        if len(filled_indices) == 0:
            # Фолбэк на центральную строку, если низ оказался затенен
            best_y = int(top_y + bar_height // 2)
            filled_indices = np.where(mask[best_y] > 0)[0]
            if len(filled_indices) == 0:
                return None

        start_x = int(filled_indices[0])
        end_x = int(filled_indices[-1])
        
        # Небольшой внутренний отступ (на 1-2 пикселя), чтобы не сканировать саму рамку бара
        return start_x + 1, end_x - 1, best_y

    def process_zone(self, zone_key, bar_types):
        raw_path = os.path.join(self.debug_dir, f"raw_{zone_key}.png")
        if not os.path.exists(raw_path):
            print(f"[Пропуск] Зона {zone_key} не найдена в дебаг-кадрах.")
            return

        img = cv2.imread(raw_path)
        img_display = img.copy()
        
        raw_zones = self.config_data.get("raw_zones", {})
        if zone_key not in raw_zones:
            print(f"[Ошибка] Координаты для {zone_key} отсутствуют в конфиге.")
            return
            
        zone_x, zone_y, zone_w, zone_h = raw_zones[zone_key]
        self.config_data.setdefault("calibrated_profiles", {}).setdefault(zone_key, {})

        print(f"\n[Анализ] Сканирование зоны '{zone_key}'...")

        for bar in bar_types:
            result = self.find_bar_by_color(img, bar)
            if result:
                start_x_rel, end_x_rel, y_rel = result
                
                # Переводим относительные координаты кропа в абсолютные экранные
                abs_start_x = zone_x + start_x_rel
                abs_end_x = zone_x + end_x_rel
                abs_y = zone_y + y_rel
                
                # Записываем финальные точки в конфиг
                self.config_data["calibrated_profiles"][zone_key][f"{bar}_start"] = [abs_start_x, abs_y]
                self.config_data["calibrated_profiles"][zone_key][f"{bar}_end"] = [abs_end_x, abs_y]
                
                print(f"  -> [{bar.upper()}] успешно откалиброван! Линия Y:{y_rel} (относительно окна)")
                
                # Дебаг-отрисовка: зеленая линия чистого сканирования
                cv2.line(img_display, (start_x_rel, y_rel), (end_x_rel, y_rel), (0, 255, 0), 1)
                
                # Наносим 6 проверочных точек матрицы
                steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
                for step in steps:
                    pt_x = int(start_x_rel + (end_x_rel - start_x_rel) * step)
                    cv2.circle(img_display, (pt_x, y_rel), 2, (0, 0, 255), -1)
            else:
                print(f"  -> [{bar.upper()}] полоса не найдена. Проверь корректность выделения зоны.")

        # Сохраняем результат
        detected_path = os.path.join(self.debug_dir, f"detected_{zone_key}.png")
        cv2.imwrite(detected_path, img_display)
        print(f"[Успех] Создан размеченный снимок: {detected_path}")

    def run_analysis(self):
        if not self.config_data.get("raw_zones"):
            print("[Ошибка] Нет сырых данных зон. Запусти сначала Этап 1.")
            return
            
        has_summon = self.config_data["game_windows"].get("has_summon", False)
        
        self.process_zone("target_mob", ["hp"])
        self.process_zone("player_status", ["cp", "hp", "mp"])
        
        if has_summon:
            self.process_zone("summon_status", ["hp", "mp"])
            
        self._save_config()
        print("\n=== АНАЛИЗ ЗАВЕРШЕН ===")
        print("Проверь новые картинки в auto_calibrator/debug_images/ с префиксом detected_")

if __name__ == "__main__":
    analyzer = ZoneAnalyzer()
    analyzer.run_analysis()
