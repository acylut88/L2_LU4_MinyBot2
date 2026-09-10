# auto_calibrator/defense_manager.py
"""
полностью изолируем логику использования банок, эликсиров и кулдаунов

"""


import asyncio
import time


class DefenseManager:
    def __init__(self, combat_profile, screen_bus):
        self.combat_profile = combat_profile
        self.bus = screen_bus
        self.is_paused = False
        self.cooldowns = {}

    def check_cooldown(self, action_id, cooldown_ms) -> bool:
        now = time.time() * 1000
        last_time = self.cooldowns.get(action_id, 0)
        if now - last_time >= cooldown_ms:
            self.cooldowns[action_id] = now
            return True
        return False

    async def hardware_press_log(self, key, label):
        print(f"[ЗАЩИТА] Прожата кнопка '{key}' -> {label} | Мой HP: {self.bus.states['player_hp']}")

    async def start_loop(self):
        print("[Защита] Фоновый поток автоматического отхила и банок запущен.")
        cfg = self.combat_profile.get("consumables_and_defense", {})
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
                
            # Проверка ХП Банок
            for pot in cfg.get("hp_potions", []):
                if pot.get("enabled") and self.bus.states["player_hp"] in ["1-20%", "20-40%", "40-60%", "60-80%"]:
                    if self.check_cooldown(f"hp_pot_{pot['key']}", pot["cooldown_ms"]):
                        await self.hardware_press_log(pot["key"], "Использование HP Банки")

            # Проверка ЦП Банок
            for cp_pot in cfg.get("cp_potions", []):
                if cp_pot.get("enabled") and self.bus.states["player_cp"] in ["1-20%", "20-40%", "40-60%"]:
                    if self.check_cooldown(f"cp_pot_{cp_pot['key']}", cp_pot["cooldown_ms"]):
                        await self.hardware_press_log(cp_pot["key"], "Использование CP Банки")
                        
            await asyncio.sleep(0.1)
