# auto_calibrator/universal_core.py
import os
import json
import asyncio
import sys
import time

from auto_calibrator.screen_bus import ScreenBus
from auto_calibrator.defense_manager import DefenseManager

class UniversalBotCore:
    def __init__(self, calibrator_name="calibrator.json", profile_name="combat_profile.json"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.calibrator_path = os.path.join(self.base_dir, "auto_calibrator", calibrator_name)
        self.profile_path = os.path.join(self.base_dir, "combat_profiles", profile_name)
        
        self.calibrator_data = self._load_json(self.calibrator_path)
        self.combat_profile = self._load_json(self.profile_path)
        
        self.bus = ScreenBus(self.calibrator_data, self.combat_profile)
        self.defense = DefenseManager(self.combat_profile, self.bus)
        
        self.is_paused = False
        self.spoil_attempted = False
        self.sweep_done = False
        
        # Состояние посадки персонажа
        self.is_sitting = False  
        self.sit_time_start = 0.0 # Время начала медитации

        # Хранилище ХП на прошлом кадре для отслеживания урона при отдыхе
        self.last_player_hp = "100%" 
        
        # Матрица весов для сравнения текстовых диапазонов шкал
        self.hp_weights = {
            "0% (МЕРТВ)": 0, "1-20%": 1, "20-40%": 2, 
            "40-60%": 3, "60-80%": 4, "80-100%": 5, "100%": 6
        }

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"[Критическая Ошибка] Файл не найден: {path}")
        sys.exit(1)

    async def hardware_press_log(self, key, label):
        print(f"[БОЙ] Нажата кнопка '{key}' -> {label} | МП: {self.bus.states['player_mp']} | ХП Моба: {self.bus.states['mob_hp']}")

    async def check_mana_and_rest(self, current_mob_hp):
        """
        Утилита контроля маны с защитой от нападения во время отдыха (Пункт 11 ТЗ + Фикс Агров).
        """
        cfg = self.combat_profile.get("consumables_and_defense", {}).get("sit_rest_setup", {})
        core = self.combat_profile.get("core_actions", {})
        if not cfg.get("enabled"):
            return False

        current_mp = self.bus.states["player_mp"]
        current_hp = self.bus.states["player_hp"]

        # ВЕСОВАЯ ПРОВЕРКА НА ПОЛУЧЕНИЕ УРОНА (ЕСЛИ МЫ СИДИМ)
        if self.is_sitting:
            weight_now = self.hp_weights.get(current_hp, 6)
            weight_last = self.hp_weights.get(self.last_player_hp, 6)
            
            if weight_now < weight_last:
                print(f"[ТРЕВОГА] Нас атаковали во время отдыха! ХП упало с {self.last_player_hp} до {current_hp}.")
                print("[Защита] Игра автоматически подняла персонажа. Отменяем режим отдыха, вступаем в бой!")
                self.is_sitting = False
                self.last_player_hp = current_hp
                
                # Мгновенно срываемся в контратаку
                await self.hardware_press_log(core["next_target"]["key"], "ВЫНУЖДЕННЫЙ КОНТР-ТАРГЕТ ПРИ АГРЕ")
                return False # Возвращаем False, чтобы боевой цикл не спал, а сразу пошел крутить скиллы

            # Запоминаем текущее ХП для следующего кадра внутри отдыха
            self.last_player_hp = current_hp

            # Встаем только если мана полная И мы отсидели минимум 5 секунд (защита от ложных кадров)
            if current_mp in ["80-100%", "100%"] and (time.time() - self.sit_time_start >= 5.0):
                print("[Отдых] Мана полностью восстановлена. Встаем.")
                await self.hardware_press(cfg["sit_stand_key"], "ВСТАТЬ (Команда Num*)")
                self.is_sitting = False
                await asyncio.sleep(1.2)
                return False
            else:
                if self.defense.check_cooldown("sit_log", 2500):
                    print(f"[Медитация] Восстановление... Мой HP: {current_hp} | MP: {current_mp}")
                return True

        # Сохраняем ХП перед потенциальной посадкой
        self.last_player_hp = current_hp

        # Если мы стоим и мана упала в ноль
        if current_mp in ["0% (МЕРТВ)", "1-20%"]:
            if current_mob_hp == "100%":
                print("[Отдых] Мана на нуле, но пойман таргет! Сбрасываем цель перед посадкой.")
                await self.hardware_press_log("Esc", "Сброс опасного таргета")
                await asyncio.sleep(0.5)
                return True 

            if current_mob_hp == "0% (МЕРТВ)":
                print("[Отдых] Поляна чистая. Садимся на реген.")
                await self.hardware_press(cfg["sit_stand_key"], "СЕСТЬ на отдых")
                self.is_sitting = True
                self.sit_time_start = time.time() # Запоминаем время посадки
                await asyncio.sleep(1.2)
                return True

        return False

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

            # Вызываем нашу умную проверку отдыха с защитой от урона
            if await self.check_mana_and_rest(current_mob_hp):
                await asyncio.sleep(0.1)
                continue
            
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
                await asyncio.sleep(0.5) 
                continue

            # --- ФАЗА АКТИВНОГО БОЯ ---
            self.sweep_done = False 
            self.is_sitting = False # Гарантируем статус "стоим" во время драки
            
            # Прожатие Спойла на старте
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
        
        await asyncio.gather(
            self.bus.start_loop(),
            self.defense.start_loop(),
            self.combat_main_loop()
        )

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bot = UniversalBotCore()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n[Движок] Модульный движок успешно остановлен.")
