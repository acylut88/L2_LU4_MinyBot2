import os
import json
import cv2
from vision.state_tracker import StateTracker
from vision.action_definitions import CombatAction, DEFAULT_MAGE_DWARF_MAP

class BaseCombat:
    def __init__(self, tracker: StateTracker, validator, arduino, buff_system=None):
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        self.buff_system = buff_system
        self.bot_manager = None
        self.is_paused = False
        
        vision_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(vision_dir, "config.json")
        
        # Директории для графических шаблонов максимального ХП
        self.white_list_dir = os.path.join(vision_dir, "vision", "white_list")
        self.black_list_dir = os.path.join(vision_dir, "vision", "black_list")
        
        os.makedirs(self.white_list_dir, exist_ok=True)
        os.makedirs(self.black_list_dir, exist_ok=True)
        
        # Загружаем графические файлы фильтров ХП один раз при старте
        self.white_templates = self._load_filter_templates(self.white_list_dir)
        self.black_templates = self._load_filter_templates(self.black_list_dir)
        
        self.action_map = self._load_action_mapping()
        
        self.player_hp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_hp")
        self.player_mp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_mp")
        self.player_hp_tracker.load_profile()
        self.player_mp_tracker.load_profile()

    def _load_filter_templates(self, dir_path: str) -> list:
        """Загружает картинки макс ХП из папки в черно-белом формате."""
        templates = []
        try:
            for file_name in os.listdir(dir_path):
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    full_path = os.path.join(dir_path, file_name)
                    img = cv2.imread(full_path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        templates.append((file_name, img))
            if templates:
                print(f"[Фильтр] Успешно кэшировано шаблонов ({len(templates)}) из: {os.path.basename(dir_path)}")
            return templates
        except Exception as e:
            print(f"[Фильтр] Критическая ошибка чтения папки {dir_path}: {e}")
            return []

    def validate_mob_by_filters(self, frame_np) -> bool:
        """Графическая верификация максимального ХП моба по откалиброванной зоне filter_zones."""
        if not self.white_templates and not self.black_templates:
            return True

        # Считываем сохраненную ручную зону фильтрации из config.json
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            zone = config.get("filter_zones", {}).get(self.tracker.profile_name)
            if not zone:
                return True # Если зона еще не размечена, временно пропускаем фильтр
            log_x, log_y, log_w, log_h = zone
        except Exception:
            return True
            
        try:
            # DPI фикс для приведения логических координат из json к пикселям физического кадра
            import win32api
            import win32con
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            img_h, img_w, _ = frame_np.shape
            dpi_factor_x = img_w / screen_w
            dpi_factor_y = img_h / screen_h
            
            x = int(log_x * dpi_factor_x)
            y = int(log_y * dpi_factor_y)
            w = int(log_w * dpi_factor_x)
            h = int(log_h * dpi_factor_y)
            
            # Вырезаем область точных цифр максимального ХП
            roi_gray = cv2.cvtColor(frame_np[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)

            # 1. Проверка по Черному Списку
            for name, template in self.black_templates:
                if roi_gray.shape[0] >= template.shape[0] and roi_gray.shape[1] >= template.shape[1]:
                    res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val >= 0.85:
                        print(f"[Фильтр] Моб ИГНОРИРУЕТСЯ: Найдено совпадение в Black-листе ({name}, совпадение: {max_val:.2f})")
                        return False

            # 2. Проверка по Белому Списку
            if self.white_templates:
                for name, template in self.white_templates:
                    if roi_gray.shape[0] >= template.shape[0] and roi_gray.shape[1] >= template.shape[1]:
                        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        if max_val >= 0.85:
                            print(f"[Фильтр] Моб ОДОБРЕН: Совпадение с White-листом ({name}, совпадение: {max_val:.2f})")
                            return True
                print("[Фильтр] Моб ИГНОРИРУЕТСЯ: Данное ХП отсутствует в White-листе.")
                return False

            return True
        except Exception as e:
            print(f"[Фильтр] Ошибка сопоставления шаблонов ХП: {e}")
            return True

    def _load_action_mapping(self) -> dict:
        current_map = DEFAULT_MAGE_DWARF_MAP.copy()
        if not os.path.exists(self.config_path):
            return current_map
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            saved_actions = config.get("mage_dwarf_settings", {}).get("combat_actions", {})
            for enum_action in CombatAction:
                if enum_action.name in saved_actions:
                    current_map[enum_action] = saved_actions[enum_action.name]
            return current_map
        except Exception:
            return current_map

    async def execute_action(self, action: CombatAction):
        button = self.action_map.get(action)
        if button:
            await self.arduino.send_button(button)
        else:
            print(f"[Движок] Предупреждение: Действие {action.name} не привязано к кнопке!")

    def set_trackers_sleep(self, is_sleep: bool):
        self.player_hp_tracker.is_paused = is_sleep
        self.player_mp_tracker.is_paused = is_sleep
