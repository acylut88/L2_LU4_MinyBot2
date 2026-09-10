# auto_calibrator/universal_core.py   Главный оркестратор
import os
import json
import asyncio
import sys
import time

# Импортируем наши логические подфайлы
from auto_calibrator.screen_bus import ScreenBus
from auto_calibrator.defense_manager import DefenseManager

class UniversalBotCore:
    def __init__(self, calibrator_name="calibrator.json", profile_name="combat_profile.json"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.calibrator_path = os.path.join(self.base_dir, "auto_calibrator", calibrator_name)
        self.profile_path = os.path.join(self.base_dir, "combat_profiles", profile_name)
        
        # Считываем переехавшие JSON файлы
        self.calibrator_data = self._load_json(self.calibrator_path)
        self.combat_profile = self._load_json(self.profile_path)
        
        # Инициализируем модули
        self.bus = ScreenBus(self.calibrator_data, self.combat_profile)
        self.defense = DefenseManager(self.combat_profile, self.bus)
        
        self.is_paused = False
        self.spoil_attempted = False
        self.sweep_done = False

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"[Критическая Ошибка] Файл не найден: {path}")
        sys.exit(1)

    async def hardware_press_log(self, key, label):
        print(f"[БОЙ] Нажата кнопка '{key}' -> {label} | ХП Моба: {self.bus.states['mob_hp']}")

    async def combat_main_loop(self):
        print("[Бой] Главный конечный автомат боевого цикла запущен.")
        core = self.combat_profile.get("core_actions", {})
        dwarf = self.combat_profile.get("dwarf_spoiler_logic", {})
        rotation = self.combat_profile.get("combat_rotation", {})
        flags = self.combat_profile.get("features_flags", {})
        
        while True:
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
                
            current_mob_hp = self.bus.states["mob_hp"]
            
            # --- ФАЗА ПОИСКА, СВИПА И СБОРА ЛУТА ---
            if current_mob_hp == "0% (МЕРТВ)":
                if flags.get("use_dwarf_logic") and dwarf.get("sweep_setup", {}).get("enabled") and not self.sweep_done:
                    sweep = dwarf["sweep_setup"]
                    for _ in range(sweep["clicks_count"]):
                        await self.hardware_press_log(sweep["key"], "Свип трупа гномом")
                        await asyncio.sleep(sweep["delay_between_clicks_ms"] / 1000)
                    self.sweep_done = True
                    
                if flags.get("loot_collection"):
                    loot = core["loot_key"]
                    for _ in range(loot["clicks_per_mob"]):
                        await self.hardware_press_log(loot["key"], "Сбор дропа (F1)")
                        await asyncio.sleep(loot["delay_ms"] / 1000)

                self.spoil_attempted = False
                await self.hardware_press_log(core["next_target"]["key"], "Поиск новой цели (F2)")
                await asyncio.sleep(0.4) 
                continue

            # --- ФАЗА АКТИВНОГО БОЯ ---
            self.sweep_done = False 
            
            # Прожатие Спойла на старте (Гном)
            if flags.get("use_dwarf_logic") and dwarf.get("spoil_setup", {}).get("enabled") and not self.spoil_attempted:
                spoil = dwarf["spoil_setup"]
                if spoil["trigger_condition"] == "on_start" and current_mob_hp == "100%":
                    for _ in range(spoil["max_attempts"]):
                        await self.hardware_press_log(spoil["key"], "Прожатие СПОЙЛА")
                        await asyncio.sleep(spoil["delay_between_attempts_ms"] / 1000)
                    self.spoil_attempted = True

            # Условие Оверхита
            if current_mob_hp == "1-20%":
                for oh in rotation.get("overhit_skills", []):
                    if oh.get("enabled") and self.defense.check_cooldown(f"oh_{oh['key']}", oh["cooldown_ms"]):
                        await self.hardware_press_log(oh["key"], "💥 ОВЕР-ХИТ (Добивание)")

            # Спам дополнительных атак по кулдаунам
            for atk in rotation.get("additional_attacks", []):
                if atk.get("enabled") and self.defense.check_cooldown(f"atk_{atk['key']}", atk["cooldown_ms"]):
                    await self.hardware_press_log(atk["key"], "Дополнительная атака класса")

            # Обычный нюк / удар в паузах
            if self.defense.check_cooldown("normal_attack", 600):
                await self.hardware_press_log(core["normal_attack"]["key"], "Базовая атака / Скилл")
                
            await asyncio.sleep(0.1)

    async def run(self):
        print("=" * 60)
        print("   ЗАПУСК МОДУЛЬНОГО АСИНХРОННОГО ДВИЖКА (ОТЛАДКА)   ")
        print("=" * 60)
        
        # Запускаем все три подсистемы параллельно
        await asyncio.gather(
            self.bus.start_loop(),
            self.defense.start_loop(),
            self.combat_main_loop()
        )

if __name__ == "__main__":
    # Фикс для корректного импорта при запуске напрямую как скрипта
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bot = UniversalBotCore()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n[Движок] Модульный движок успешно остановлен.")
