# version2/auto_calibrator/universal_core.py
import os
import json
import asyncio
import sys
import time

from auto_calibrator.screen_bus import ScreenBus
from auto_calibrator.defense_manager import DefenseManager
from auto_calibrator.approach_control import ApproachControl
from auto_calibrator.combat_rotation import CombatRotation

class UniversalBotCore:
    def __init__(self, calibrator_name="calibrator.json", profile_name="combat_profile.json"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.calibrator_path = os.path.join(self.base_dir, "auto_calibrator", calibrator_name)
        self.profile_path = os.path.join(self.base_dir, "combat_profiles", profile_name)
        
        self.calibrator_data = self._load_json(self.calibrator_path)
        self.combat_profile = self._load_json(self.profile_path)
        
        self.bus = ScreenBus(self.calibrator_data, self.combat_profile)
        self.defense = DefenseManager(self.combat_profile, self.bus)
        self.approach = ApproachControl(self) 
        self.rotation = CombatRotation(self) # Подключаем боевую ротацию
        
        self.is_paused = False
        self.spoil_attempted = False
        self.sweep_done = False
        self.loot_done = False       
        self.is_sitting = False  
        self.sit_time_start = 0.0 
        self.last_player_hp = "100%" 
        self.f2_fail_count = 0          

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        sys.exit(1)

    async def hardware_press_log(self, key, label):
        mp_val = self.bus.states['player_mp']
        hp_val = self.bus.states['mob_hp']
        print(f"[БОЙ] Кнопка '{key}' -> {label} | MP: {mp_val} | Моб: {hp_val}")

    async def check_mana_and_rest(self, current_mob_hp):
        cfg = self.combat_profile.get("consumables_and_defense", {}).get("sit_rest_setup", {})
        core = self.combat_profile.get("core_actions", {})
        if not cfg.get("enabled"): return False

        current_mp = self.bus.states["player_mp"]
        current_hp = self.bus.states["player_hp"]

        if self.is_sitting:
            if self.approach.hp_weights.get(current_hp, 6) < self.approach.hp_weights.get(self.last_player_hp, 6):
                self.is_sitting = False
                self.last_player_hp = current_hp
                await self.hardware_press_log(core["next_target"]["key"], "АНТИ-АГР ВСТАТЬ")
                return False 

            self.last_player_hp = current_hp

            if current_mp in ["80-100%", "100%"] and (time.time() - self.sit_time_start >= 5.0):
                await self.hardware_press_log(cfg["sit_stand_key"], "ВСТАТЬ")
                self.is_sitting = False
                await asyncio.sleep(1.2)
                return False
            else:
                if self.defense.check_cooldown("sit_log", 2500):
                    print(f"[Медитация] Свободный реген... HP: {current_hp} | MP: {current_mp}")
                return True

        self.last_player_hp = current_hp

        if current_mp in ["0% (МЕРТВ)", "1-20%"]:
            if current_mob_hp != "0% (МЕРТВ)":
                await self.hardware_press_log("Esc", "Сброс таргета перед посадкой")
                self.bus.states["mob_hp"] = "0% (МЕРТВ)"
                await asyncio.sleep(0.4)
                return True 

            if current_mob_hp == "0% (МЕРТВ)":
                await self.hardware_press_log(cfg["sit_stand_key"], "СЕСТЬ")
                self.is_sitting = True
                self.sit_time_start = time.time() 
                await asyncio.sleep(1.2)
                return True
        return False

    async def combat_main_loop(self):
        print("[Бой] Главный конечный автомат боевого цикла запущен.")
        core = self.combat_profile.get("core_actions", {})
        dwarf = self.combat_profile.get("dwarf_spoiler_logic", {})
        flags = self.combat_profile.get("features_flags", {})
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
                
            current_mob_hp = self.bus.states["mob_hp"]
            current_player_hp = self.bus.states["player_hp"]

            if await self.check_mana_and_rest(current_mob_hp):
                await asyncio.sleep(0.1)
                continue
            
            # --- ФАЗА ПОИСКА, СВИПА И СБОРА ЛУТА ---
            if current_mob_hp == "0% (МЕРТВ)":
                self.approach.is_approaching = False
                self.approach.monitor_search_damage(current_player_hp)

                if flags.get("use_dwarf_logic") and dwarf.get("sweep_setup", {}).get("enabled") and not self.sweep_done:
                    sweep = dwarf["sweep_setup"]
                    for _ in range(sweep["clicks_count"]):
                        await self.hardware_press_log(sweep["key"], "Свип")
                        await asyncio.sleep(sweep["delay_between_clicks_ms"] / 1000)
                    self.sweep_done = True
                    
                if flags.get("loot_collection") and not self.loot_done:
                    loot = core["loot_key"]
                    for _ in range(loot["clicks_per_mob"]):
                        await self.hardware_press_log(loot["key"], "Лут F1")
                        await asyncio.sleep(loot["delay_ms"] / 1000)
                    self.loot_done = True

                self.spoil_attempted = False

                # Стягивание маяком
                f2_threshold = core.get("long_range_pull", {}).get("f2_fails_threshold", 5)
                if self.f2_fail_count >= f2_threshold:
                    self.f2_fail_count = 0  
                    await self.hardware_press_log(core["long_range_pull"]["key"], "Маяк 0")
                    await asyncio.sleep(0.45)
                    if self.bus.states["mob_hp"] != "0% (МЕРТВ)":
                        await self.hardware_press_log(core["normal_attack"]["key"], "Бег к маяку")
                        await asyncio.sleep(1.2)
                        await self.hardware_press_log("Esc", "Сброс маяка")
                        await asyncio.sleep(0.1)
                        for _ in range(3):
                            await self.hardware_press_log(core["next_target"]["key"], "F2 на ходу")
                            await asyncio.sleep(0.2)
                            if self.bus.states["mob_hp"] != "0% (МЕРТВ)": break
                    continue

                if self.defense.check_cooldown("empty_spot_f2", 250):
                    await self.hardware_press_log(core["next_target"]["key"], "Поиск F2")
                    await asyncio.sleep(0.15)
                    if self.bus.states["mob_hp"] == "0% (МЕРТВ)": self.f2_fail_count += 1
                
                await asyncio.sleep(0.05) 
                continue

            # --- ФАЗА АКТИВНОГО БОЯ ---
            self.sweep_done = False 
            self.loot_done = False 
            self.is_sitting = False 
            self.f2_fail_count = 0  
            self.last_player_hp = current_player_hp

            # Проверка вежливого фарма / самообороны
            if current_mob_hp != "100%" and flags.get("skip_damaged_mobs"):
                if self.approach.under_attack_on_search:
                    self.approach.under_attack_on_search = False
                else:
                    await self.hardware_press_log("Esc", "Пропуск раненого")
                    self.bus.states["mob_hp"] = "0% (МЕРТВ)"
                    await asyncio.sleep(0.4)
                    continue

            if await self.approach.handle_approach_logic(current_mob_hp):
                continue

            # ДЕЛЕГИРОВАНИЕ: Передаем выполнение скиллов нашему новому модулю
            await self.rotation.execute_skills(current_mob_hp)
            await asyncio.sleep(0.1)

    async def run(self):
        print("=" * 60)
        print("   ЗАПУСК МОДУЛЬНОГО АСИНХРОННОГО ДВИЖКА (ОТЛАДКА)   ")
        print("=" * 60)
        await asyncio.gather(
            self.bus.start_loop(),
            self.defense.start_loop(),
            self.combat_main_loop()
        )

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bot = UniversalBotCore()
    try: asyncio.run(bot.run())
    except KeyboardInterrupt: print("\n[Выход]")
