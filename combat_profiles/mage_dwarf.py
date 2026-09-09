import asyncio
import random
from vision.combat_base import BaseCombat
from vision.action_definitions import CombatAction

class Mage_dwarfCombat(BaseCombat):
    def __init__(self, tracker, validator, arduino, buff_system=None):
        super().__init__(tracker, validator, arduino, buff_system)
        self.aggressive_mode = True
        self.is_resting = False
        
        # ФИКС БАГА №2: Увеличиваем таймаут до 15 сек, чтобы не скипать мобов на 5-10% ХП
        self.combat_timeout = 15.0       
        self.search_delay = 0.07
        self.empty_spot_delay = 0.5
        self.f2_fail_count = 0
        
        # Удержание отката лечащего скилла кнопка "3"
        self.last_hp_skill_time = 0 

    async def _check_mana_and_recharge(self):
        current_mp = self.player_mp_tracker.get_current_value()
        if current_mp < 20:
            if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Dual-Box":
                support_role = getattr(self.bot_manager, 'support_mode', 0)
                if support_role in self.buff_system.MODES_WITH_RECHARGE:
                    self.set_trackers_sleep(True)
                    await self.bot_manager.request_recharge()
                    self.set_trackers_sleep(False)
                    await asyncio.sleep(1.0)
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
        """Логика работы дальнего маяка стягивания."""
        print(f"[Маяк] На споте долго пусто. Прожимаем экшен дальнего поиска ACTION_LONG_PULL...")
        self.f2_fail_count = 0
        await self.execute_action(CombatAction.ACTION_LONG_PULL)
        
        current_mob_hp = 0
        for i in range(10):
            await asyncio.sleep(0.1)
            current_mob_hp = self.tracker.get_current_value()
            if current_mob_hp > 0: 
                break
            
        if current_mob_hp > 0:
            if await self.validator.is_boss_selected():
                print("[Маяк] ВНИМАНИЕ! Дальний макрос выделил БОССА! Отмена...")
                await self.execute_action(CombatAction.ACTION_CANCEL_TARGET)
                return False
                
            current_frame = self.tracker._current_frame
            if current_frame is not None and not self.validate_mob_by_filters(current_frame):
                print("[Маяк -> Фильтр] Дальний моб отклонен фильтром ХП. Сбрасываем...")
                await self.execute_action(CombatAction.ACTION_CANCEL_TARGET)
                await asyncio.sleep(0.15)
                return False

            print("[Маяк] Дальняя цель одобрена фильтром. Инициируем движение персонажа...")
            await self.execute_action(CombatAction.ACTION_NUKE_1)
            await asyncio.sleep(0.15)
            await self.execute_action(CombatAction.ACTION_HAND_ATTACK)
            
            await asyncio.sleep(1.0) 
            await self.execute_action(CombatAction.ACTION_CANCEL_TARGET)
            await asyncio.sleep(0.1)
            return True
            
        print("[Маяк] По макросу дальнего поиска никто не нашелся.")
        return False

    async def _initiate_combat(self, current_mob_hp, start_time) -> int:
        max_seen_hp = current_mob_hp
        while current_mob_hp == max_seen_hp:
            if self.is_paused: break
            if asyncio.get_event_loop().time() - start_time >= 5.0:
                break
            await self.execute_action(CombatAction.ACTION_NUKE_1)
            await asyncio.sleep(random.uniform(0.1, 0.2))
            await self.execute_action(CombatAction.ACTION_HAND_ATTACK)
            await asyncio.sleep(random.uniform(0.1, 0.2))
            current_mob_hp = self.tracker.get_current_value()
        return current_mob_hp

    async def _combat_processing(self, current_mob_hp, start_combat_time):
        """Внутренний цикл ведения боя. Синхронизирован с Шиной Кадров."""
        while current_mob_hp > 0:
            # ФИКС БАГА №3: Стабильный замер (50 мс), чтобы дать трекерам ХП/МП считать кадр экрана
            await asyncio.sleep(0.05)
            if self.is_paused: continue
            
            # Контур самосохранения дварфа (ХП скилл кнопка "3")
            current_player_hp = self.player_hp_tracker.get_current_value()
            if current_player_hp <= 80:
                now = asyncio.get_event_loop().time()
                if now - self.last_hp_skill_time >= 7.0:
                    print(f"[Выживание] ХП упало до {current_player_hp}%. Юзаем ХП-скилл (ACTION_HP_SKILL)...")
                    await self.execute_action(CombatAction.ACTION_HP_SKILL)
                    self.last_hp_skill_time = now
                    await asyncio.sleep(0.2) 
            
            # Получаем свежее ХП моба
            current_mob_hp = self.tracker.get_current_value()

            # Проверка защитного таймаута боя
            if asyncio.get_event_loop().time() - start_combat_time >= self.combat_timeout:
                print("[Бой] Превышен таймаут убийства моба. Сбрасываем таргет...")
                await self.execute_action(CombatAction.ACTION_CANCEL_TARGET)
                break

            # Добивание овер-хитом
            if 0 < current_mob_hp <= 20:
                print(f"[Добивание] ХП моба {current_mob_hp}%. Пробиваем ACTION_OVER_HIT!")
                await self.execute_action(CombatAction.ACTION_OVER_HIT)
                while self.tracker.get_current_value() > 0:
                    await asyncio.sleep(0.05)
                break
            
            # Ротация спама основным атакующим скиллом
            if current_mob_hp > 20:
                await self.execute_action(CombatAction.ACTION_NUKE_1)
                await asyncio.sleep(0.2)

    async def start_loop(self):
        print(f"\n[Бой] Профиль Маг-Дварф запущен. Линейный агрессивный сценарий фарма активен.")
        asyncio.create_task(self.player_hp_tracker.track_loop())
        asyncio.create_task(self.player_mp_tracker.track_loop())
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(0.2)
                    continue

                # 1. Проверка маны перед поиском
                await self._check_mana_and_recharge()
                current_mob_hp = self.tracker.get_current_value()
                
                # 2. Поиск цели при ХП = 0
                if current_mob_hp == 0:
                    if self.buff_system:
                        self.set_trackers_sleep(True)
                        await self.buff_system.check_and_run_pending_buffs()
                        self.set_trackers_sleep(False)

                    if self.is_paused: continue
                    
                    if self.f2_fail_count >= 5:
                        if await self._handle_beacon_pulling(): 
                            continue
                    
                    await self.execute_action(CombatAction.ACTION_NEXT_TARGET)
                    await asyncio.sleep(0.25)
                    
                    current_mob_hp = self.tracker.get_current_value()
                    if current_mob_hp == 0:
                        self.f2_fail_count += 1
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                # 3. Валидация найденного моба через графический фильтр
                current_frame = self.tracker._current_frame
                if current_frame is not None:
                    if current_mob_hp >= 90:
                        if not self.validate_mob_by_filters(current_frame):
                            print("[Фильтр] Моб НЕ прошел проверку Белого списка. Пропускаем...")
                            await self.execute_action(CombatAction.ACTION_CANCEL_TARGET)
                            self.f2_fail_count += 1
                            await asyncio.sleep(0.2)
                            continue

                # 4. Вход в боевой контур
                self.f2_fail_count = 0
                print(f"[Таргет] Цель зафиксирована. Начинаем уничтожение. ХП моба: {current_mob_hp}%.")
                start_combat_time = asyncio.get_event_loop().time()
                
                current_mob_hp = await self._initiate_combat(current_mob_hp, start_combat_time)
                await self._combat_processing(current_mob_hp, start_combat_time)
                
                print("[Бой] Моб успешно уничтожен. Очищаем состояние для следующего цикла.\n")
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"[Ошибка] Критический сбой боевого цикла дварфа: {e}")
                await asyncio.sleep(1.0)
