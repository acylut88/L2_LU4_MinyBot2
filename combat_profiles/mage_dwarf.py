import asyncio
import random
from combat_profiles.combat_base import BaseCombat
from combat_profiles.action_definitions import CombatAction

class Mage_dwarfCombat(BaseCombat):
    def __init__(self, tracker, validator, arduino, buff_system=None):
        super().__init__(tracker, validator, arduino, buff_system)
        self.aggressive_mode = True
        self.is_resting = False
        self.combat_timeout = 7.0
        self.search_delay = 0.07
        self.empty_spot_delay = 0.5
        self.f2_fail_count = 0

    async def _check_mana_and_recharge(self):
        current_mp = self.player_mp_tracker.get_current_value()
        if current_mp < 20:
            # ВАРИАНТ А: Режим Двух окон (Dual-Box) -> Вызываем заливку от саппорта
            if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Dual-Box":
                support_role = getattr(self.bot_manager, 'support_mode', 0)
                
                # Проверяем роль через список констант в buff_system (без хардкода цифр)
                if support_role in self.buff_system.MODES_WITH_RECHARGE:
                    self.set_trackers_sleep(True)
                    await self.bot_manager.request_recharge()
                    self.set_trackers_sleep(False)
                    await asyncio.sleep(1.0)
            
            # ВАРИАНТ Б: Режим Одного окна (Single-Box / Соло) -> Садимся на жопу
            else:
                if not self.is_resting:
                    print(f"\n[Регенерация Соло] Мана мало: {current_mp}%. Садимся (Экшен ACTION_SIT_STAND)...")
                    self.is_resting = True
                    await self.execute_action(CombatAction.ACTION_SIT_STAND)
                    
                    while self.is_resting:
                        await asyncio.sleep(2.0)
                        if self.is_paused: continue
                        if self.player_mp_tracker.get_current_value() >= 80:
                            print("[Регенерация Соло] Мана восполнена! Встаем...")
                            await self.execute_action(CombatAction.ACTION_SIT_STAND)
                            self.is_resting = False
                            await asyncio.sleep(1.0)


    async def _handle_beacon_pulling(self) -> bool:
        """Метод-подфайл: Логика работы дальнего маяка стягивания."""
        print(f"[Маяк] Прожимаем дальнее стягивание (Экшен ACTION_LONG_PULL)...")
        self.f2_fail_count = 0
        await self.execute_action(CombatAction.ACTION_LONG_PULL)
        
        current_mob_hp = 0
        for i in range(12):
            await asyncio.sleep(0.1)
            current_mob_hp = self.tracker.get_current_value()
            if current_mob_hp > 0: break
            
        if current_mob_hp > 0:
            if await self.validator.is_boss_selected():
                await self.arduino.send_button("Esc")
                return False
                
            print("[Маяк] Дальняя цель зацеплена. Начинаем инерционный подбег...")
            await self.execute_action(CombatAction.ACTION_NUKE_1)
            await asyncio.sleep(0.15)
            await self.execute_action(CombatAction.ACTION_HAND_ATTACK)
            
            await asyncio.sleep(1.2) # Бежим вперед
            await self.arduino.send_button("Esc")
            
            for _ in range(4):
                await self.arduino.send_button("F2")
                await asyncio.sleep(0.2)
                if self.tracker.get_current_value() > 0: return True
        return False

    async def _initiate_combat(self, current_mob_hp, start_time) -> int:
        """Метод-подфайл: Фаза инициации и пробития геодаты спота."""
        max_seen_hp = current_mob_hp
        while current_mob_hp == max_seen_hp:
            if self.is_paused: break
            if asyncio.get_event_loop().time() - start_time >= 10.0:
                await self.arduino.send_button("Esc")
                break
            await self.execute_action(CombatAction.ACTION_NUKE_1)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await self.execute_action(CombatAction.ACTION_HAND_ATTACK)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            current_mob_hp = self.tracker.get_current_value()
        return current_mob_hp

    async def _combat_processing(self, current_mob_hp, start_time):
        """Метод-подфайл: Фаза основного циклического сражения и добивания."""
        while current_mob_hp > 0:
            await asyncio.sleep(0.05)
            if self.is_paused: continue
            current_mob_hp = self.tracker.get_current_value()

            if asyncio.get_event_loop().time() - start_time >= self.combat_timeout:
                await self.arduino.send_button("Esc")
                break

            # Умное агрессивное добивание через Овер-хит на 20% ХП моба
            if 0 < current_mob_hp <= 20:
                print(f"[Добивание] ХП моба {current_mob_hp}%. Пробиваем ACTION_OVER_HIT!")
                await self.execute_action(CombatAction.ACTION_OVER_HIT)
                while self.tracker.get_current_value() > 0:
                    await asyncio.sleep(0.05)
                break
            
            if current_mob_hp > 20:
                await self.execute_action(CombatAction.ACTION_NUKE_1)
                await asyncio.sleep(0.2)

    async def start_loop(self):
        print(f"\n[Бой] Профиль Маг-Дварф запущен. Унифицированная схема активна.")
        asyncio.create_task(self.player_hp_tracker.track_loop())
        asyncio.create_task(self.player_mp_tracker.track_loop())
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(0.2)
                    continue

                await self._check_mana_and_recharge()
                current_mob_hp = self.tracker.get_current_value()
                
                if current_mob_hp == 0:
                    if self.is_paused: continue
                    if self.buff_system:
                        self.set_trackers_sleep(True)
                        await self.buff_system.check_and_run_pending_buffs()
                        self.set_trackers_sleep(False)

                    if self.is_paused: continue
                    
                    # Триггер дальнего маяка стягивания
                    if self.f2_fail_count >= 5:
                        if await self._handle_beacon_pulling(): continue
                        
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    current_mob_hp = self.tracker.get_current_value()
                    if current_mob_hp == 0:
                        self.f2_fail_count += 1
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                self.f2_fail_count = 0
                print(f"[Таргет] Цель найдена. ХП моба: {current_mob_hp}%. Начинаем атаку...")
                start_combat_time = asyncio.get_event_loop().time()
                
                # Запуск подфайлов-методов инициации и драки
                current_mob_hp = await self._initiate_combat(current_mob_hp, start_combat_time)
                await self._combat_processing(current_mob_hp, start_combat_time)
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"[Ошибка] Критический сбой боевого цикла дварфа: {e}")
                await asyncio.sleep(1.0)
