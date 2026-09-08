import asyncio
import random
from vision.state_tracker import StateTracker
from vision.target_validator import TargetValidator
from vision.target_puller import TargetPuller
from arduino.arduino_controller_async import AsyncArduinoController

class OverlordCombat:
    def __init__(self, tracker: StateTracker, validator: TargetValidator, arduino: AsyncArduinoController, buff_system=None):
        """
        Класс управления боевой логикой Оверлорда.
        """
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        self.buff_system = buff_system  
        
        self.puller = TargetPuller(self.tracker, self.arduino)
        self.is_paused = False
        
        # Конфигурация боевых таймингов
        self.combat_timeout = 20.0       
        self.search_delay = 0.07         
        self.empty_spot_delay = 0.5      
        self.escape_delay = 0.1          
        self.loot_delay = 0.05           
        self.pet_tank_delay = 0.5        

        self.f2_fail_count = 0

    async def start_loop(self):
        print("\n[Бой] Класс Суммонер успешно запущен. Входим в боевой цикл...")
        self.tracker.check_interval = 0.1
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(0.2)
                    continue

                # Шаг 1: Проверяем наличие цели в таргете
                current_hp = self.tracker.get_current_hp()
                
                if current_hp == 0:
                    if self.is_paused: continue
                    
                    # === ЗАЩИЩЕННЫЙ РЕБАФФ МЕЖДУ МОБАМИ ===
                    if self.buff_system and hasattr(self.buff_system, 'check_and_run_pending_buffs'):
                        await self.buff_system.check_and_run_pending_buffs()
                    # ======================================

                    if self.is_paused: continue
                    
                    # ПРОВЕРКА КОНТР-ФИЧИ ДАЛЬНЕГО ПУЛЛЕРА (5 фейлов F2)
                    if self.f2_fail_count >= 5 or await self.puller.execute_pulling(self.validator, init_attack_keys=["1", "F4"]):
                        self.f2_fail_count = 0 
                        continue
                    
                    # ШТАТНЫЙ РЕЖИМ ПОИСКА ПО F2
                    print("[Поиск] Цели нет. МГНОВЕННЫЙ поиск моба (Нажимаем F2)...")
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    current_hp = self.tracker.get_current_hp()
                    if current_hp == 0:
                        self.puller.register_f2_fail()
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                self.puller.reset_f2_fails()

                 # Шаг 2: Анализ состояния найденной цели
                print(f"[Таргет] Обнаружена цель. Текущее ХП моба: {current_hp}%")
                
                # Логика вежливого фарма раненых мобов
                if current_hp < 100:
                    if self.is_paused: continue
                    
                    if getattr(self, 'allow_damaged_mob', False):
                        print("[Защита] Повторный раненый моб на споте. Включаем режим ожидания (2 сек)...")
                        self.allow_damaged_mob = False
                        
                        start_wait = asyncio.get_event_loop().time()
                        is_someone_attacking = False
                        last_damaged_hp = current_hp
                        
                        while asyncio.get_event_loop().time() - start_wait < 2.0:
                            await asyncio.sleep(0.2)
                            if self.is_paused: break
                            
                            check_hp = self.tracker.get_current_hp()
                            if check_hp < last_damaged_hp and check_hp > 0:
                                print(f"[Защита] ХП моба падает ({check_hp}% < {last_damaged_hp}%)! Его бьют. Пропускаем спот...")
                                is_someone_attacking = True
                                break
                                
                        if self.is_paused: continue
                        
                        if is_someone_attacking:
                            await self.arduino.send_button("Esc")
                            await asyncio.sleep(self.empty_spot_delay)
                            continue
                        else:
                            print("[Защита] ХП стабильно в течение 2 сек. Моб наш! Принимаем бой...")
                            current_hp = self.tracker.get_current_hp()
                    
                    else:
                        print("[Защита] Первый раненый моб. Пропускаем через F2 и взводим флаг защиты...")
                        await self.arduino.send_button("F2")
                        await asyncio.sleep(self.search_delay)
                        self.allow_damaged_mob = True
                        continue
                else:
                    self.allow_damaged_mob = False

                # Шаг 3: Проверка на босса (череп)
                is_boss = await self.validator.is_boss_selected()
                if is_boss:
                    print("[Защита] ВНИМАНИЕ! ОБНАРУЖЕН БОСС (ЧЕРЕП)! Сбрасываем таргет...")
                    await self.arduino.send_button("Esc") 
                    await asyncio.sleep(self.escape_delay)
                    continue

                # Шаг 4: ШТАТНАЯ АТАКА
                print("[Бой] Цель одобрена! Начинаем атаку дрыньконем ХП...")
                await self.arduino.send_button("1") 
                await asyncio.sleep(self.pet_tank_delay)
                print("[Бой] Начинаем атаку персонажем...")
                await self.arduino.send_button("F4")   
                
                start_combat_time = asyncio.get_event_loop().time()
                last_attack_time = start_combat_time
                max_seen_hp = current_hp
                
                # Внутренний цикл сражения
                while True:
                    await asyncio.sleep(0.05)
                    if self.is_paused:
                        await asyncio.sleep(0.2)
                        continue
                        
                    current_hp = self.tracker.get_current_hp()
                    now = asyncio.get_event_loop().time()
                    
                    if current_hp == 0:
                        print("[Бой] Моб повержен! МГНОВЕННЫЙ сбор лута...")
                        loot_clicks = random.randint(3, 5)
                        for _ in range(loot_clicks):
                            if self.is_paused: break
                            await self.arduino.send_button("F1")
                            await asyncio.sleep(self.loot_delay) 
                        print("[Бой] Сбор завершен. Освобождаем поток для следующей цели.")
                        break
                    
                    if now - start_combat_time >= self.combat_timeout:
                        print("[Таймаут] Застряли. Сброс цели...")
                        await self.arduino.send_button("Esc")
                        await asyncio.sleep(self.loot_delay)
                        break
                    
                    if current_hp < max_seen_hp:
                        max_seen_hp = current_hp
                        last_attack_time = now  
                    
                    if now - last_attack_time >= random.uniform(1.0, 4.0):
                        if self.is_paused: continue
                        print("[Бой] ХП моба не падает. Повторное прожатие атаки...")
                        await self.arduino.send_button("1")
                        last_attack_time = now

            except Exception as e:
                print(f"[Критическая ошибка] Ошибка в боевом цикле сумонера: {e}")
                await asyncio.sleep(1.0)
