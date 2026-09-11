# version2/auto_calibrator/approach_control.py
import time
import asyncio

class ApproachControl:
    def __init__(self, core):
        self.core = core # Ссылка на главный оркестратор
        self.approach_start_time = 0.0
        self.is_approaching = False
        self.under_attack_on_search = False
        
        self.hp_weights = {
            "0% (МЕРТВ)": 0, "1-20%": 1, "20-40%": 2, 
            "40-60%": 3, "60-80%": 4, "80-100%": 5, "100%": 6
        }

    def monitor_search_damage(self, current_player_hp):
        """Следит за ударами со спины в фазе поиска."""
        weight_now = self.hp_weights.get(current_player_hp, 6)
        weight_last = self.hp_weights.get(self.core.last_player_hp, 6)
        
        if weight_now < weight_last:
            print(f"[САМООБОРОНА] Входящий урон на поиске! HP упало с {self.core.last_player_hp} до {current_player_hp}.")
            self.under_attack_on_search = True
            
        self.core.last_player_hp = current_player_hp

    async def handle_approach_logic(self, current_mob_hp) -> bool:
        """
        Контролирует 7 секунд бега до моба (анти-затык).
        Возвращает True, если цель была экстренно сброшена.
        """
        if current_mob_hp == "100%":
            self.under_attack_on_search = False 
            if not self.is_approaching:
                print("[Сближение] Цель взята. Старт 7-секундного таймера анти-затыка...")
                self.approach_start_time = time.time()
                self.is_approaching = True
            else:
                if time.time() - self.approach_start_time >= 7.0:
                    print("[Сближение] Затык в текстуре! Бежим больше 7 секунд без урона.")
                    await self.core.hardware_press("Esc", "Сброс недосягаемого моба")
                    self.core.bus.states["mob_hp"] = "0% (МЕРТВ)"
                    self.is_approaching = False
                    await asyncio.sleep(0.4)
                    return True
        else:
            if self.is_approaching:
                print("[Сближение] Урон пошел! Персонаж добежал. Таймер отключен.")
                self.is_approaching = False
        return False
