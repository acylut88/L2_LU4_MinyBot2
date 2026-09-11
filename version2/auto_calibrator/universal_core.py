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
from auto_calibrator.bot_logger import BotLogger
from auto_calibrator.bot_initializer import BotInitializer

from version2.arduino.arduino_controller_async import AsyncArduinoController
from version2.vision.target_validator import TargetValidator

class UniversalBotCore:
    def __init__(self, profile_name="combat_profile.json"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.profile_path = os.path.join(self.base_dir, "combat_profiles", profile_name)
        
        self.config_data = self._load_json(self.config_path)
        self.combat_profile = self._load_json(self.profile_path)
        
        self.logger = BotLogger()
        self.arduino = AsyncArduinoController(config_path=self.config_path)
        self.validator = TargetValidator(profile_name="NB_Moi")
        
        from auto_calibrator.screen_saver import ScreenSaver
        self.saver = ScreenSaver(self) # Подключаем скриншотер
        
        self.bus = ScreenBus(self.config_data, self.combat_profile)
        self.defense = DefenseManager(self.combat_profile, self.bus, self.arduino)
        self.approach = ApproachControl(self) 
        self.rotation = CombatRotation(self)
        self.initializer = BotInitializer(self) 
        
        self.is_paused = False
        self.spoil_attempted = False
        self.sweep_done = False
        self.loot_done = False       
        self.is_sitting = False  
        self.sit_time_start = 0.0 
        self.last_player_hp = "100%" 
        self.f2_fail_count = 0          
        self.combat_started = False 

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        sys.exit(1)

    async def hardware_press(self, key, label):
        mp_val = self.bus.states['player_mp']
        hp_val = self.bus.states['mob_hp']
        print(f"[HARDWARE] Кнопка '{key}' -> {label} | MP: {mp_val} | Моб: {hp_val}")
        await self.arduino.send_button(key)

    async def check_mana_and_rest(self, current_mob_hp):
        """Утилита контроля маны с защитой от нападения (Пункт 11 ТЗ)."""
        cfg = self.combat_profile.get("consumables_and_defense", {}).get("sit_rest_setup", {})
        core = self.combat_profile.get("core_actions", {})
        if not cfg.get("enabled"): return False

        current_mp = self.bus.states["player_mp"]
        current_hp = self.bus.states["player_hp"]

        if self.is_sitting:
            if self.approach.hp_weights.get(current_hp, 6) < self.approach.hp_weights.get(self.last_player_hp, 6):
                self.logger.log_event("CRITICAL", f"Агр на медитации! HP упало до {current_hp}.")
                self.is_sitting = False
                self.last_player_hp = current_hp
                await self.hardware_press(core["next_target"]["key"], "АНТИ-АГР ВСТАТЬ")
                return False 

            self.last_player_hp = current_hp

            if current_mp in ["80-100%", "100%"] and (time.time() - self.sit_time_start >= 5.0):
                await self.hardware_press(cfg["sit_stand_key"], "ВСТАТЬ (Num*)")
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
                await self.hardware_press("Esc", "Сброс таргета перед посадкой")
                self.bus.states["mob_hp"] = "0% (МЕРТВ)"
                await asyncio.sleep(0.4)
                return True 

            if current_mob_hp == "0% (МЕРТВ)":
                self.logger.log_event("WARNING", "Низкая мана (<20%). Посадка.")
                await self.hardware_press(cfg["sit_stand_key"], "СЕСТЬ (Num*)")
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

            if current_player_hp == "0% (МЕРТВ)":
                self.logger.log_event("DEATH", "ВНИМАНИЕ! Персонаж погиб.")
                self.saver.save_snapshot("DEATH") # Скриншот смерти
                self.is_paused = True
                await asyncio.sleep(5.0)
                continue

            if await self.check_mana_and_rest(current_mob_hp):
                await asyncio.sleep(0.1)
                continue
            
            # --- ФАЗА ПОИСКА, СВИПА И СБОРА ЛУТА ---
            if current_mob_hp == "0% (МЕРТВ)":
                self.approach.is_approaching = False
                self.approach.monitor_search_damage(current_player_hp)
                self.combat_started = False 

                if flags.get("use_dwarf_logic") and dwarf.get("sweep_setup", {}).get("enabled") and not self.sweep_done:
                    sweep = dwarf["sweep_setup"]
                    for _ in range(sweep["clicks_count"]):
                        await self.hardware_press(sweep["key"], "Свип трупа")
                        await asyncio.sleep(sweep["delay_between_clicks_ms"] / 1000)
                    self.sweep_done = True
                    
                if flags.get("loot_collection") and not self.loot_done:
                    loot = core["loot_key"]
                    for _ in range(loot["clicks_per_mob"]):
                        await self.hardware_press(loot["key"], "Сбор лута F1")
                        await asyncio.sleep(loot["delay_ms"] / 1000)
                    self.loot_done = True

                self.spoil_attempted = False

                f2_threshold = core.get("long_range_pull", {}).get("f2_fails_threshold", 5)
                if self.f2_fail_count >= f2_threshold:
                    self.f2_fail_count = 0  
                    await self.hardware_press(core["long_range_pull"]["key"], "Дальний Маяк 0")
                    await asyncio.sleep(0.45)
                    if self.bus.states["mob_hp"] != "0% (МЕРТВ)":
                        await self.hardware_press(core["normal_attack"]["key"], "Бег к маяку")
                        await asyncio.sleep(2.2)
                        await self.hardware_press("Esc", "Сброс маяка")
                        await asyncio.sleep(0.1)
                        for _ in range(3):
                            await self.hardware_press(core["next_target"]["key"], "F2 на ходу")
                            await asyncio.sleep(0.2)
                            if self.bus.states["mob_hp"] != "0% (МЕРТВ)": break
                    continue

                if self.defense.check_cooldown("empty_spot_f2", 250):
                    await self.hardware_press(core["next_target"]["key"], "Поиск Next Target F2")
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

            if not self.combat_started:
                if current_mob_hp != "100%" and flags.get("skip_damaged_mobs"):
                    if self.approach.under_attack_on_search:
                        self.approach.under_attack_on_search = False
                        self.combat_started = True 
                    else:
                        await self.hardware_press("Esc", "Пропуск раненого моба")
                        self.bus.states["mob_hp"] = "0% (МЕРТВ)"
                        await asyncio.sleep(0.4)
                        continue
                else:
                    self.combat_started = True

            if current_mob_hp in ["100%", "80-100%"] and flags.get("boss_protection"):
                if await self.validator.is_boss_selected():
                    self.logger.log_event("BOSS", "Обнаружен БОСС! Сброс.")
                    await self.hardware_press("Esc", "Сброс босса")
                    self.bus.states["mob_hp"] = "0% (МЕРТВ)"
                    self.combat_started = False
                    await asyncio.sleep(0.4)
                    continue

            if await self.approach.handle_approach_logic(current_mob_hp):
                self.combat_started = False
                continue

            await self.rotation.execute_skills(current_mob_hp)
            await asyncio.sleep(0.05)

    async def run(self):
        await self.initializer.run_system()
