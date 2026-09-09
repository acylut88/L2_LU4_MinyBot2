import os
import json
import asyncio
from vision.state_tracker import StateTracker
from combat_profiles.action_definitions import CombatAction, DEFAULT_MAGE_DWARF_MAP

class BaseCombat:
    def __init__(self, tracker: StateTracker, validator, arduino, buff_system=None):
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        self.buff_system = buff_system
        self.bot_manager = None
        self.is_paused = False
        
        # Динамические пути конфигурации
        vision_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(vision_dir, "config.json")
        
        # Карта кнопок экшенов конкретного профиля
        self.action_map = self._load_action_mapping()
        
        # Персональные трекеры
        self.player_hp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_hp")
        self.player_mp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_mp")
        self.player_hp_tracker.load_profile()
        self.player_mp_tracker.load_profile()

    def _load_action_mapping(self) -> dict:
        """Считывает привязку экшенов к физическим кнопкам игры."""
        current_map = DEFAULT_MAGE_DWARF_MAP.copy()
        if not os.path.exists(self.config_path):
            return current_map
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            saved_actions = config.get("mage_dwarf_settings", {}).get("combat_actions", {})
            
            # Сопоставляем строковые ключи из JSON с Enum объектами Python
            for enum_action in CombatAction:
                if enum_action.name in saved_actions:
                    current_map[enum_action] = saved_actions[enum_action.name]
            return current_map
        except Exception:
            return current_map

    async def execute_action(self, action: CombatAction):
        """Безопасно отправляет команду эмуляции кнопки на базе Enum экшена."""
        button = self.action_map.get(action)
        if button:
            await self.arduino.send_button(button)
        else:
            print(f"[Движок] Предупреждение: Действие {action.name} не привязано к кнопке!")

    def set_trackers_sleep(self, is_sleep: bool):
        """Массовое управление сном трекеров персонажа при ротации окон."""
        self.player_hp_tracker.is_paused = is_sleep
        self.player_mp_tracker.is_paused = is_sleep
