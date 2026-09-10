# version2/auto_calibrator/defense_manager.py
import asyncio
import time

class DefenseManager:
    def __init__(self, combat_profile, screen_bus, arduino_controller):
        self.combat_profile = combat_profile
        self.bus = screen_bus
        self.arduino = arduino_controller # Физическая плата Leonardo
        self.is_paused = False
        self.cooldowns = {}

    def check_cooldown(self, action_id, cooldown_ms) -> bool:
        now = time.time() * 1000
        last_time = self.cooldowns.get(action_id, 0)
        if now - last_time >= cooldown_ms:
            self.cooldowns[action_id] = now
            return True
        return False

    async def execute_defense_action(self, key, label):
        print(f"[ЗАЩИТА] Физический прожим '{key}' -> {label} | Мой HP: {self.bus.states['player_hp']}")
        await self.arduino.send_button(key) # Отправляем байт в COM-порт

    async def start_loop(self):
        print("[Защита] Фоновый поток аппаратного отхила и банок запущен.")
        cfg = self.combat_profile.get("consumables_and_defense", {})
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
                
            # Проверка ХП Банок (Кулдаун изменен на 10 секунд)
            for pot in cfg.get("hp_potions", []):
                if pot.get("enabled") and self.bus.states["player_hp"] in ["1-20%", "20-40%", "40-60%", "60-80%"]:
                    if self.check_cooldown(f"hp_pot_{pot['key']}", 10000): # 10000 мс = 10 сек
                        await self.execute_defense_action(pot["key"], "Использование HP Банки")

            # Проверка ЦП Банок
            for cp_pot in cfg.get("cp_potions", []):
                if cp_pot.get("enabled") and self.bus.states["player_cp"] in ["1-20%", "20-40%", "40-60%"]:
                    if self.check_cooldown(f"cp_pot_{cp_pot['key']}", cp_pot["cooldown_ms"]):
                        await self.execute_defense_action(cp_pot["key"], "Использование CP Банки")
                        
            await asyncio.sleep(0.05) # Высокая частота опроса для мгновенной реакции
